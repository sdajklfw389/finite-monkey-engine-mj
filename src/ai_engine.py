from concurrent.futures import ThreadPoolExecutor
import json
import re
import threading
import time
from typing import List, Dict
import requests
import tqdm
from sklearn.metrics.pairwise import cosine_similarity
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import warnings
import urllib3
import os
warnings.filterwarnings('ignore', category=urllib3.exceptions.NotOpenSSLWarning)
from dao.entity import Project_Task
from prompt_factory.prompt_assembler import PromptAssembler
from prompt_factory.core_prompt import CorePrompt
from openai_api.openai import *
from prompt_factory.vul_prompt_common import VulPromptCommon

class DialogueHistory:
    def __init__(self, project_id: str):
        self._history = {}  # 格式: {task_name: {prompt_index: [responses]}}
        self._lock = threading.Lock()
        self.project_id = project_id
        self.base_dir = os.path.join("src", "chat_history", project_id)
        
    def _get_task_dir(self, task_name: str) -> str:
        """获取任务的目录路径"""
        return os.path.join(self.base_dir, task_name)
        
    def _get_history_file(self, task_name: str, prompt_index: int = None) -> str:
        """获取历史记录文件的路径"""
        task_dir = self._get_task_dir(task_name)
        if prompt_index is not None:
            # 对于 COMMON_PROJECT_FINE_GRAINED 模式
            return os.path.join(task_dir, str(prompt_index), "chat_history")
        return os.path.join(task_dir, "chat_history")
        
    def _ensure_dir_exists(self, directory: str):
        """确保目录存在"""
        os.makedirs(directory, exist_ok=True)
        
    def _load_history_from_file(self, task_name: str, prompt_index: int = None):
        """从文件加载历史记录"""
        history_file = self._get_history_file(task_name, prompt_index)
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️ 警告：历史记录文件 {history_file} 格式错误")
                return []
            except Exception as e:
                print(f"⚠️ 警告：读取历史记录文件 {history_file} 时出错: {str(e)}")
                return []
        return []
        
    def _save_history_to_file(self, task_name: str, responses: list, prompt_index: int = None):
        """保存历史记录到文件"""
        history_file = self._get_history_file(task_name, prompt_index)
        self._ensure_dir_exists(os.path.dirname(history_file))
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(responses, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 警告：保存历史记录到文件 {history_file} 时出错: {str(e)}")

    def add_response(self, task_name: str, prompt_index: int, response: str):
        """添加新的响应"""
        with self._lock:
            if task_name not in self._history:
                self._history[task_name] = {}
            if prompt_index not in self._history[task_name]:
                # 从文件加载已有历史
                self._history[task_name][prompt_index] = self._load_history_from_file(task_name, prompt_index)
            
            self._history[task_name][prompt_index].append(response)
            # 保存到文件
            self._save_history_to_file(task_name, self._history[task_name][prompt_index], prompt_index)

    def get_history(self, task_name: str, prompt_index: int = None) -> list:
        """获取历史记录"""
        with self._lock:
            if task_name not in self._history:
                self._history[task_name] = {}
            
            if prompt_index is not None:
                if prompt_index not in self._history[task_name]:
                    # 从文件加载历史
                    self._history[task_name][prompt_index] = self._load_history_from_file(task_name, prompt_index)
                return self._history[task_name].get(prompt_index, [])
            
            # 如果没有指定 prompt_index，加载所有历史
            all_responses = []
            history_dir = self._get_task_dir(task_name)
            if os.path.exists(history_dir):
                if os.path.exists(self._get_history_file(task_name)):
                    # 非 COMMON_PROJECT_FINE_GRAINED 模式
                    all_responses.extend(self._load_history_from_file(task_name))
                else:
                    # COMMON_PROJECT_FINE_GRAINED 模式
                    for index_dir in os.listdir(history_dir):
                        if os.path.isdir(os.path.join(history_dir, index_dir)):
                            responses = self._load_history_from_file(task_name, int(index_dir))
                            all_responses.extend(responses)
            return all_responses

    def clear(self):
        """清除所有历史记录"""
        with self._lock:
            self._history.clear()
            if os.path.exists(self.base_dir):
                import shutil
                shutil.rmtree(self.base_dir)

class AiEngine(object):

    # 添加类变量来跟踪当前的 prompt index
    current_prompt_index = 0
    # 从 VulPromptCommon 中获取实际的检查列表数量
    total_prompt_count = len(VulPromptCommon.vul_prompt_common_new().keys())

    def __init__(self, planning, taskmgr,lancedb,lance_table_name,project_audit):
        # Step 1: 获取results
        self.planning = planning
        self.project_taskmgr = taskmgr
        self.lancedb = lancedb
        self.lance_table_name = lance_table_name
        self.project_audit = project_audit
        # 实例级别的 prompt index 追踪
        self.current_prompt_index = 0
        self.total_prompt_count = len(VulPromptCommon.vul_prompt_common_new().keys())
        # 对话历史管理 - 添加 project_id
        self.dialogue_history = DialogueHistory(project_audit.project_id)

    def do_planning(self):
        self.planning.do_planning()
    def process_task_do_scan(self, task, filter_func=None, is_gpt4=False):
        response_final = ""
        response_vul = ""

        result = task.get_result(is_gpt4)
        business_flow_code = task.business_flow_code
        if_business_flow_scan = task.if_business_flow_scan
        function_code = task.content
        
        # 要进行检测的代码粒度
        code_to_be_tested = business_flow_code if if_business_flow_scan=="1" else function_code
        if result is not None and len(result) > 0 and str(result).strip() != "NOT A VUL IN RES no":
            print("\t skipped (scanned)")
        else:
            to_scan = filter_func is None or filter_func(task)
            if not to_scan:
                print("\t skipped (filtered)")
            else:
                # print("\t to scan")
                pass

            if os.getenv("SCAN_MODE","COMMON_VUL")=="OPTIMIZE":  
                prompt = PromptAssembler.assemble_optimize_prompt(code_to_be_tested)
            elif os.getenv("SCAN_MODE","COMMON_VUL")=="CHECKLIST":
                print("📋Generating checklist...")
                prompt = PromptAssembler.assemble_checklists_prompt(code_to_be_tested)
                response_checklist = cut_reasoning_content(ask_deepseek(prompt))
                print("[DEBUG🐞]📋response_checklist length: ",len(response_checklist))
                print(f"[DEBUG🐞]📋response_checklist: {response_checklist[:50]}...")
                prompt = PromptAssembler.assemble_checklists_prompt_for_scan(code_to_be_tested,response_checklist)
            elif os.getenv("SCAN_MODE","COMMON_VUL")=="CHECKLIST_PIPELINE":
                checklist = task.description
                print(f"[DEBUG🐞]📋Using checklist from task description: {checklist[:50]}...")
                prompt = PromptAssembler.assemble_prompt_for_checklist_pipeline(code_to_be_tested, checklist)
            elif os.getenv("SCAN_MODE","COMMON_VUL")=="COMMON_PROJECT":
                prompt = PromptAssembler.assemble_prompt_common(code_to_be_tested)
            elif os.getenv("SCAN_MODE","COMMON_VUL")=="COMMON_PROJECT_FINE_GRAINED":
                current_index = self.current_prompt_index
                print(f"[DEBUG🐞]📋Using prompt index {current_index} for fine-grained scan")
                prompt = PromptAssembler.assemble_prompt_common_fine_grained(code_to_be_tested, current_index)
                
                checklist_dict = VulPromptCommon.vul_prompt_common_new(current_index)
                if checklist_dict:
                    checklist_key = list(checklist_dict.keys())[0]
                    print(f"[DEBUG🐞]📋Updating recommendation with checklist key: {checklist_key}")
                    self.project_taskmgr.update_recommendation(task.id, checklist_key)
                
                self.current_prompt_index = (current_index + 1) % self.total_prompt_count
            elif os.getenv("SCAN_MODE","COMMON_VUL")=="PURE_SCAN":
                prompt = PromptAssembler.assemble_prompt_pure(code_to_be_tested)
            elif os.getenv("SCAN_MODE","COMMON_VUL")=="SPECIFIC_PROJECT":
                business_type = task.recommendation
                business_type_list = business_type.split(',')
                prompt = PromptAssembler.assemble_prompt_for_specific_project(code_to_be_tested, business_type_list)
            
            response_vul = common_ask_for_json(prompt)
            print(f"[DEBUG] Claude response: {response_vul[:50]}")
            response_vul = response_vul if response_vul is not None else "no"                
            self.project_taskmgr.update_result(task.id, response_vul, "","")
    def do_scan(self, is_gpt4=False, filter_func=None):
        # 获取任务列表
        tasks = self.project_taskmgr.get_task_list()
        if len(tasks) == 0:
            return

        # 检查是否启用对话模式
        dialogue_mode = os.getenv("ENABLE_DIALOGUE_MODE", "False").lower() == "true"
        
        if dialogue_mode:
            print("🗣️ 对话模式已启用")
            # 按task.name分组任务
            task_groups = {}
            for task in tasks:
                task_groups.setdefault(task.name, []).append(task)
            
            # 清除历史对话记录
            self.dialogue_history.clear()
            
            # 对每组任务进行处理
            max_threads = int(os.getenv("MAX_THREADS_OF_SCAN", 5))
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                # 创建每组任务的future
                futures = []
                for task_name, group_tasks in task_groups.items():
                    # 提交组任务
                    future = executor.submit(self._process_task_group, group_tasks, filter_func, is_gpt4)
                    futures.append(future)
                
                # 使用tqdm显示进度
                with tqdm(total=len(task_groups), desc="Processing task groups") as pbar:
                    for future in as_completed(futures):
                        future.result()
                        pbar.update(1)
        else:
            print("🔄 标准模式运行中")
            # 原始的多线程扫描方式
            max_threads = int(os.getenv("MAX_THREADS_OF_SCAN", 5))
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                futures = [executor.submit(self.process_task_do_scan, task, filter_func, is_gpt4) for task in tasks]
                
                with tqdm(total=len(tasks), desc="Processing tasks") as pbar:
                    for future in as_completed(futures):
                        future.result()
                        pbar.update(1)

        return tasks

    def _process_task_group(self, tasks, filter_func, is_gpt4):
        """处理同一组（相同task.name）的任务"""
        for task in tasks:
            self.process_task_do_scan_dialog(task, filter_func, is_gpt4)

    def process_task_check_vul(self, task:Project_Task):
        print("\n" + "="*80)
        print(f"🔍 开始处理任务 ID: {task.id}")
        print("="*80)
        
        # 用于收集所有分析结果
        analysis_collection = []
        
        starttime = time.time()
        result = task.get_result(False)
        result_CN = task.get_result_CN()
        category_mark = task.get_category()
        
        if result_CN is not None and len(result_CN) > 0 and result_CN != "None" and category_mark is not None and len(category_mark)>0:
            print("\n🔄 该任务已处理完成，跳过...")
            return
            
        print("\n🔍 开始漏洞确认流程...")
        print(f"📝 原始扫描结果长度: {len(result)}")
        
        function_code = task.content
        if_business_flow_scan = task.if_business_flow_scan
        business_flow_code = task.business_flow_code
        business_flow_context = task.business_flow_context
        
        code_to_be_tested = business_flow_code+"\n"+business_flow_context if if_business_flow_scan=="1" else function_code
        print(f"\n📊 分析代码类型: {'业务流程代码' if if_business_flow_scan=='1' else '函数代码'}")
        
        # 第一轮分析
        print("\n=== 第一轮分析开始 ===")
        print("📝 正在分析潜在漏洞...")
        prompt = PromptAssembler.assemble_vul_check_prompt(code_to_be_tested, result)
        

        initial_response = common_ask_confirmation(prompt)
        if not initial_response or initial_response == "":
            print(f"❌ Error: Empty response received for task {task.id}")
            return
        
        print("\n📊 Initial Analysis Result Length:")
        print("-" * 80)
        print(len(initial_response))
        print("-" * 80)

        # 收集初始分析结果
        analysis_collection.append("=== 初始分析结果 ===")
        analysis_collection.append(initial_response)

        # 对initial_response进行process_round_response处理
        initial_result_status = self.process_round_response(initial_response)
        analysis_collection.append("=== 初始分析状态 ===")
        analysis_collection.append(initial_result_status)

        # 提取所需信息
        required_info = self.extract_required_info(initial_response)
        if required_info:
            analysis_collection.append("=== 需要进一步分析的信息 ===")
            analysis_collection.extend(required_info)

        if "no" in initial_result_status:
            print("\n🛑 Initial analysis shows clear 'no vulnerability' - stopping further analysis")
            response_final = "no"
            final_response = "Analysis stopped after initial round due to clear 'no vulnerability' result"
            
            # 格式化所有收集的结果
            formatted_results = "\n\n".join(str(item or '').strip() for item in analysis_collection)
            
            # 在更新数据库之前清理字符串
            formatted_results = formatted_results.replace('\x00', '')
            
            self.project_taskmgr.update_result(task.id, result, response_final, final_response)
            self.project_taskmgr.update_category(task.id, formatted_results)
            
            endtime = time.time()
            time_cost = endtime - starttime
            print("\n=== Task Summary ===")
            print(f"⏱️ Time cost: {time_cost:.2f} seconds")
            print(f"📝 Analyses performed: 1")
            print(f"🏁 Final status Length: {len(response_final)}")
            print("=" * 80 + "\n")
            return
        
        # 设置最大确认轮数
        max_rounds = int(os.getenv("MAX_CONFIRMATION_ROUNDS", 3))
        request_per_round = int(os.getenv("REQUESTS_PER_CONFIRMATION_ROUND", 3))
        confirmation_results = []
        response_final = None
        final_response = None
        
        # 获取初始代码上下文
        current_code = code_to_be_tested
        current_response = initial_response
        
        for round_num in range(max_rounds):
            print(f"\n=== 确认轮次 {round_num + 1}/{max_rounds} ===")
            
            # 提取所需的额外信息
            required_info = self.extract_required_info(current_response)
            
            current_additional_info = []  # 用于收集本轮的所有额外信息
            
            if required_info:
                print(f"\n🔍 第 {round_num + 1} 轮需要额外信息:")
                for i, info in enumerate(required_info, 1):
                    print(f"{i}. {info}")
                
                # 获取网络搜索信息
                print("\n🌐 检查是否需要网络搜索...")
                internet_info = self.get_additional_internet_info(required_info)
                if internet_info:
                    current_additional_info.append("=== Internet Search Results ===")
                    current_additional_info.append(internet_info)
                    analysis_collection.append(f"=== 第 {round_num + 1} 轮网络搜索结果 ===")
                    analysis_collection.append(internet_info)
                
                # 获取额外上下文
                print("\n📥 正在获取额外上下文...")
                additional_context = self.get_additional_context(required_info)
                if additional_context:
                    print(f"\n📦 获取到新的上下文 (长度: {len(additional_context)} 字符)")
                    current_additional_info.append("=== Additional Context ===")
                    current_additional_info.append(additional_context)
                    analysis_collection.append(f"=== 第 {round_num + 1} 轮额外上下文 ===")
                    analysis_collection.append(additional_context)
            
            # 组合所有额外信息
            if current_additional_info:
                current_code = "\n\n".join(current_additional_info)
            
            # 使用当前上下文进行确认
            print(f"\n📊 使用当前上下文进行第 {round_num + 1} 轮确认...")
            prompt = PromptAssembler.assemble_vul_check_prompt_final(current_code, result)
            round_response = ""
            for request_num in range(request_per_round):
                print(f"\n🔍 第 {request_num + 1} / {request_per_round} 次询问")
                sub_round_response = common_ask_confirmation(prompt)
            
                print(f"\n📋 第 {request_num + 1} 次询问结果长度: {len(sub_round_response)}")
            
                # 收集分析结果
                analysis_collection.append(f"=== 第 {round_num + 1} 轮 {request_num + 1} 次询问分析结果 ===")
                analysis_collection.append(sub_round_response)
            
                # 处理响应结果
                if len(sub_round_response) == 0:
                    print(f"\n❌ 无效的响应: 第 {round_num + 1} 轮 {request_num + 1} 次询问结果为空")
                    continue
                sub_result_status = self.process_round_response(sub_round_response)
                analysis_collection.append(f"=== 第 {round_num + 1} 轮 {request_num + 1} 次分析状态 ===")
                print(f"=== 第 {round_num + 1} 轮 {request_num + 1} 次分析状态 ===") # @debug
                analysis_collection.append(sub_result_status)
                print(sub_result_status) # @debug
            
                confirmation_results.append(sub_result_status)
                round_response += sub_round_response + "\n"

                # 检查是否有明确的"no"结果
                if "no" in sub_result_status:
                    print("\n🛑 发现明确的'无漏洞'结果 - 停止进一步分析")
                    response_final = "no"
                    final_response = f"分析在第 {round_num + 1} 轮 {request_num + 1} 次询问后停止，因为发现明确的'无漏洞'结果"
                    break
            
            current_response = round_response  # 更新当前响应用于下一轮分析
        
        # 只有在没有提前退出的情况下才进行多数投票
        if response_final != "no":
            # 统计结果
            yes_count = sum(1 for r in confirmation_results if "yes" in r or "confirmed" in r)
            no_count = sum(1 for r in confirmation_results if "no" in r and "vulnerability" in r)
            
            if yes_count >= 2:
                response_final = "yes"
                print("\n⚠️ 最终结果: 漏洞已确认 (2+ 次确认)")
            elif no_count >= 2:
                response_final = "no"
                print("\n✅ 最终结果: 无漏洞 (2+ 次否定)")
            else:
                response_final = "not sure"
                print("\n❓ 最终结果: 不确定 (结果不明确)")
            
            final_response = "\n".join([f"Round {i+1} Analysis:\n{resp}" for i, resp in enumerate(confirmation_results)])
        
        # 添加最终结论
        analysis_collection.append("=== 最终结论 ===")
        analysis_collection.append(f"结果: {response_final}")
        analysis_collection.append(f"详细说明: {final_response}")
        
        # 格式化所有收集的结果
        formatted_results = "\n\n".join(str(item or '').strip() for item in analysis_collection)
        
        # 在更新数据库之前清理字符串
        formatted_results = formatted_results.replace('\x00', '')
        
        self.project_taskmgr.update_result(task.id, result, response_final, final_response)
        self.project_taskmgr.update_category(task.id, formatted_results)
        
        endtime = time.time()
        time_cost = endtime - starttime
        
        print("\n=== Task Summary ===")
        print(f"⏱️ Time cost: {time_cost:.2f} seconds")
        print(f"📝 Analyses performed: {len(confirmation_results)}")
        print(f"🏁 Final status Length: {len(response_final)}")
        print("=" * 80 + "\n")

    def process_round_response(self, round_response):
        """
        处理每轮分析的响应，提取结果状态，增加防御性编程
        
        Args:
            round_response: 当前轮次的响应
            
        Returns:
            str: 提取的结果状态
        """
        prompt_translate_to_json = PromptAssembler.brief_of_response()
        
        # 使用 common_ask_for_json 获取 JSON 响应
        round_json_response = str(common_ask_for_json(round_response+"\n"+prompt_translate_to_json))
        print("\n📋 JSON Response Length:")
        print(len(round_json_response))
        
        try:
            cleaned_response = round_json_response
            print(f"\n🔍 清理后的响应: {cleaned_response}")
            
            # 解析 JSON
            response_data = json.loads(cleaned_response)
            
            # 获取结果状态，使用 get 方法提供默认值
            result_status = response_data.get("result", "not sure").lower()
            
            print(f"\n🎯 提取的结果状态: {result_status}")
            print(f"📏 结果状态长度: {len(result_status)}")
            print(f"\n📝 完整响应内容: {cleaned_response}")
            
            # 验证结果状态的有效性
            valid_statuses = {"yes", "no", "need creator to decide", "confirmed"}
            if not any(status in result_status for status in valid_statuses):
                print("\n⚠️ 无效的结果状态 - 标记为 'not sure'")
                return "not sure"
            
            return result_status
        
        except json.JSONDecodeError as e:
            print(f"\n⚠️ JSON 解析错误: {str(e)} - 标记为 'not sure'")
            return "not sure"
        except Exception as e:
            print(f"\n⚠️ 意外错误: {str(e)} - 标记为 'not sure'")
            return "not sure"

    def get_related_functions(self,query,k=3):
        query_embedding = common_get_embedding(query)
        table = self.lancedb.open_table(self.lance_table_name)
        return table.search(query_embedding).limit(k).to_list()
    
    def extract_related_functions_by_level(self, function_names: List[str], level: int) -> str:
        """
        从call_trees中提取指定函数相关的上下游函数信息并扁平化处理
        
        Args:
            function_names: 要分析的函数名列表
            level: 要分析的层级深度
            
        Returns:
            str: 所有相关函数内容的拼接文本
        """
        def get_functions_from_tree(tree, current_level=0, max_level=level, collected_funcs=None, level_stats=None):
            """递归获取树中指定层级内的所有函数信息"""
            if collected_funcs is None:
                collected_funcs = []
            if level_stats is None:
                level_stats = {}
                
            if not tree or current_level > max_level:
                return collected_funcs, level_stats
                    
            # 添加当前节点的函数信息
            if tree['function_data']:
                collected_funcs.append(tree['function_data'])
                # 更新层级统计
                level_stats[current_level] = level_stats.get(current_level, 0) + 1
                    
            # 递归处理子节点
            if current_level < max_level:
                for child in tree['children']:
                    get_functions_from_tree(child, current_level + 1, max_level, collected_funcs, level_stats)
                        
            return collected_funcs, level_stats

        all_related_functions = []
        statistics = {
            'total_layers': level,
            'upstream_stats': {},
            'downstream_stats': {}
        }
        
        # 使用集合进行更严格的去重
        seen_functions = set()  # 存储函数的唯一标识符
        unique_functions = []   # 存储去重后的函数
        
        # 遍历每个指定的函数名
        for func_name in function_names:
            # 在call_trees中查找对应的树
            for tree_data in self.project_audit.call_trees:
                if tree_data['function'] == func_name:
                    # 处理上游调用树
                    if tree_data['upstream_tree']:
                        upstream_funcs, upstream_stats = get_functions_from_tree(tree_data['upstream_tree'])
                        all_related_functions.extend(upstream_funcs)
                        # 合并上游统计信息
                        for level, count in upstream_stats.items():
                            statistics['upstream_stats'][level] = (
                                statistics['upstream_stats'].get(level, 0) + count
                            )
                            
                    # 处理下游调用树
                    if tree_data['downstream_tree']:
                        downstream_funcs, downstream_stats = get_functions_from_tree(tree_data['downstream_tree'])
                        all_related_functions.extend(downstream_funcs)
                        # 合并下游统计信息
                        for level, count in downstream_stats.items():
                            statistics['downstream_stats'][level] = (
                                statistics['downstream_stats'].get(level, 0) + count
                            )
                        
                    # 添加原始函数本身
                    for func in self.project_audit.functions_to_check:
                        if func['name'].split('.')[-1] == func_name:
                            all_related_functions.append(func)
                            break
                                
                    break
        
        # 增强的去重处理
        for func in all_related_functions:
            # 创建一个更精确的唯一标识符，包含函数名和内容的hash
            func_identifier = f"{func['name']}_{hash(func['content'])}"
            if func_identifier not in seen_functions:
                seen_functions.add(func_identifier)
                unique_functions.append(func)
        
        # 拼接所有函数内容，包括状态变量
        combined_text_parts = []
        for func in unique_functions:
            # 查找对应的状态变量
            state_vars = None
            for tree_data in self.project_audit.call_trees:
                if tree_data['function'] == func['name'].split('.')[-1]:
                    state_vars = tree_data.get('state_variables', '')
                    break
            
            # 构建函数文本，包含状态变量
            function_text = []
            if state_vars:
                function_text.append("// Contract State Variables:")
                function_text.append(state_vars)
                function_text.append("\n// Function Implementation:")
            function_text.append(func['content'])
            
            combined_text_parts.append('\n'.join(function_text))
        
        combined_text = '\n\n'.join(combined_text_parts)
        
        # 打印统计信息
        print(f"\nFunction Call Tree Statistics:")
        print(f"Total Layers Analyzed: {level}")
        print("\nUpstream Statistics:")
        for layer, count in statistics['upstream_stats'].items():
            print(f"Layer {layer}: {count} functions")
        print("\nDownstream Statistics:")
        for layer, count in statistics['downstream_stats'].items():
            print(f"Layer {layer}: {count} functions")
        print(f"\nTotal Unique Functions: {len(unique_functions)}")
        
        return combined_text


    def check_function_vul(self):
        # self.llm.init_conversation()
        tasks = self.project_taskmgr.get_task_list()
        # 用codebaseQA的形式进行，首先通过rag和task中的vul获取相应的核心三个最相关的函数
        for task in tqdm(tasks,desc="Processing tasks for update business_flow_context"):
            if task.score=="1":
                continue
            if task.if_business_flow_scan=="1":
                # 获取business_flow_context
                code_to_be_tested=task.business_flow_code
            else:
                code_to_be_tested=task.content

            # 添加重试逻辑
            max_retries = 3
            retry_count = 0
            combined_text = ""

            while retry_count < max_retries:
                related_functions=self.get_related_functions(code_to_be_tested,5)
                related_functions_names=[func['name'].split('.')[-1] for func in related_functions]
                combined_text=self.extract_related_functions_by_level(related_functions_names,2)
                print(len(str(combined_text).strip()))
                
                if len(str(combined_text).strip()) >= 10:
                    break  # 如果获取到有效上下文，就跳出循环
                
                retry_count += 1
                print(f"❌ 提取的上下文长度不足10字符，正在重试 ({retry_count}/{max_retries})...")
            
            # 重试后仍未获取有效上下文
            if len(str(combined_text).strip()) < 10:
                print(f"❌ 经过{max_retries}次重试后，仍未能获取有效上下文，跳过该任务")
                continue
                
            # 更新task对应的business_flow_context
            self.project_taskmgr.update_business_flow_context(task.id,combined_text)
            self.project_taskmgr.update_score(task.id,"1")
            

        if len(tasks) == 0:
            return

        # 定义线程池中的线程数量, 从env获取
        max_threads = int(os.getenv("MAX_THREADS_OF_CONFIRMATION", 5))

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = [executor.submit(self.process_task_check_vul, task) for task in tasks]

            with tqdm(total=len(tasks), desc="Checking vulnerabilities") as pbar:
                for future in as_completed(futures):
                    future.result()  # 等待每个任务完成
                    pbar.update(1)  # 更新进度条

        return tasks

    def extract_required_info(self, claude_response):
        """Extract information that needs further investigation from Claude's response"""
        # prompt = """
        # Please extract all information points that need further understanding or confirmation from the following analysis response.
        # If the analysis explicitly states "no additional information needed" or similar, return empty.
        # If the analysis mentions needing more information, extract these information points.
        
        # Analysis response:
        # {response}
        # """
        prompt = CorePrompt.extract_required_info_prompt()
        
        extraction_result = ask_claude(prompt.format(response=claude_response))
        if not extraction_result or extraction_result.isspace():
            return []
        
        # If response contains negative phrases, return empty list
        if any(phrase in extraction_result.lower() for phrase in ["no need", "not needed", "no additional", "no more"]):
            return []
        
        return [extraction_result]

    def get_additional_context(self, query_contents):
        """获取额外的上下文信息"""
        if not query_contents:
            print("❌ 没有查询内容，无法获取额外上下文")
            return ""
        
        print(f"🔍 正在查询 {len(query_contents)} 条相关信息...")
        related_functions = []
        for query in query_contents:
            results = self.get_related_functions(query, k=10)
            if results:
                print(f"✅ 找到 {len(results)} 个相关函数")
                related_functions.extend(results)
            else:
                print("⚠️ 未找到相关函数")
        
        if related_functions:
            function_names = [func['name'].split('.')[-1] for func in related_functions]
            print(f"📑 正在提取 {len(function_names)} 个函数的上下文...")
            return self.extract_related_functions_by_level(function_names, 2)
        
        print("❌ 未找到任何相关函数")
        return ""

    def get_additional_internet_info(self, required_info):
        """判断是否需要联网搜索并获取网络信息
        
        Args:
            required_info: 需要进一步调查的信息列表
            
        Returns:
            str: 搜索获取的相关信息
        """
        # 检查环境变量是否允许网络搜索
        if os.getenv("ENABLE_INTERNET_SEARCH", "False").lower() != "True":
            print("❌ 网络搜索已禁用")
            return ""
        
        if not required_info:
            print("❌ 没有查询内容，无法进行网络搜索")
            return ""
        
        # 构建判断是否需要联网搜索的提示词
        # judge_prompt = """
        # Please analyze if the following information points require internet search to understand better.
        # The information might need internet search if it involves:
        # 1. Technical concepts or protocols that need explanation
        # 2. Specific vulnerabilities or CVEs
        # 3. Industry standards or best practices
        # 4. Historical incidents or known attack vectors
        
        # Return ONLY a JSON response in this exact format, with no additional text:
        # {{
        #     "needs_search": "yes/no",
        #     "reason": "brief explanation"
        # }}
        
        # Information to analyze:
        # {0}
        # """
        judge_prompt = CorePrompt.judge_prompt()
        
        # 将所有required_info合并成一个查询文本
        combined_query = "\n".join(required_info)
        
        # 获取判断结果
        judge_response = ask_claude(judge_prompt.format(combined_query))
        print("\n🔍 网络搜索需求分析:")
        print(judge_response)
        
        try:
            # 尝试提取JSON部分 - 只匹配第一个完整的JSON对象
            import re
            # 使用非贪婪匹配来获取第一个完整的JSON对象
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', judge_response)
            if json_match:
                json_str = json_match.group(0)
                # 清理可能的额外字符
                json_str = json_str.strip()
                judge_result = json.loads(json_str)
            else:
                raise json.JSONDecodeError("No JSON found in response", judge_response, 0)
                
            if judge_result.get("needs_search", "no").lower() == "yes":
                print(f"\n🌐 需要网络搜索: {judge_result.get('reason', '')}")
                
                # 使用 grok 进行深度搜索
                search_results = ask_grok3_deepsearch(combined_query)
                if search_results:
                    print(f"\n✅ 获取到网络搜索结果 (长度: {len(search_results)} 字符)")
                    return search_results
                else:
                    print("\n⚠️ 网络搜索未返回有效结果")
                    return ""
            else:
                print(f"\n📝 无需网络搜索: {judge_result.get('reason', '')}")
                return ""
            
        except json.JSONDecodeError:
            print("\n⚠️ JSON 解析错误 - 跳过网络搜索")
            return ""

    def process_task_do_scan_dialog(self, task, filter_func=None, is_gpt4=False):
        """对话模式下的任务扫描处理"""
        response_final = ""
        response_vul = ""

        result = task.get_result(is_gpt4)
        business_flow_code = task.business_flow_code
        if_business_flow_scan = task.if_business_flow_scan
        function_code = task.content
        
        # 要进行检测的代码粒度
        code_to_be_tested = business_flow_code if if_business_flow_scan=="1" else function_code
        
        if result is not None and len(result) > 0 and str(result).strip() != "NOT A VUL IN RES no":
            print("\t skipped (scanned)")
            return
            
        to_scan = filter_func is None or filter_func(task)
        if not to_scan:
            print("\t skipped (filtered)")
            return
            
        print("\t to scan")

        # 获取当前prompt_index（对于COMMON_PROJECT_FINE_GRAINED模式）
        current_index = self.current_prompt_index if os.getenv("SCAN_MODE","COMMON_VUL")=="COMMON_PROJECT_FINE_GRAINED" else None

        # 获取历史对话
        dialogue_history = self.dialogue_history.get_history(task.name, current_index)
        
        print(f"\n🔄 Task: {task.name}")
        print(f"📊 历史对话数量: {len(dialogue_history)}")
        
        # 打印历史对话长度统计
        if dialogue_history:
            print("\n📈 历史对话长度统计:")
            for i, hist in enumerate(dialogue_history, 1):
                print(f"  第{i}轮对话长度: {len(hist)} 字符")
        
        # 生成基础prompt
        if os.getenv("SCAN_MODE","COMMON_VUL")=="OPTIMIZE":  
            prompt = PromptAssembler.assemble_optimize_prompt(code_to_be_tested)
        elif os.getenv("SCAN_MODE","COMMON_VUL")=="CHECKLIST":
            print("📋Generating checklist...")
            prompt = PromptAssembler.assemble_checklists_prompt(code_to_be_tested)
            response_checklist = cut_reasoning_content(ask_deepseek(prompt))
            print("[DEBUG🐞]📋response_checklist length: ",len(response_checklist))
            print(f"[DEBUG🐞]📋response_checklist: {response_checklist[:50]}...")
            prompt = PromptAssembler.assemble_checklists_prompt_for_scan(code_to_be_tested,response_checklist)
        elif os.getenv("SCAN_MODE","COMMON_VUL")=="CHECKLIST_PIPELINE":
            checklist = task.description
            print(f"[DEBUG🐞]📋Using checklist from task description: {checklist[:50]}...")
            prompt = PromptAssembler.assemble_prompt_for_checklist_pipeline(code_to_be_tested, checklist)
        elif os.getenv("SCAN_MODE","COMMON_VUL")=="COMMON_PROJECT":
            prompt = PromptAssembler.assemble_prompt_common(code_to_be_tested)
        elif os.getenv("SCAN_MODE","COMMON_VUL")=="COMMON_PROJECT_FINE_GRAINED":
            print(f"[DEBUG🐞]📋Using prompt index {current_index} for fine-grained scan")
            prompt = PromptAssembler.assemble_prompt_common_fine_grained(code_to_be_tested, current_index)
            
            checklist_dict = VulPromptCommon.vul_prompt_common_new(current_index)
            if checklist_dict:
                checklist_key = list(checklist_dict.keys())[0]
                print(f"[DEBUG🐞]📋Updating recommendation with checklist key: {checklist_key}")
                self.project_taskmgr.update_recommendation(task.id, checklist_key)
            
            self.current_prompt_index = (current_index + 1) % self.total_prompt_count
        elif os.getenv("SCAN_MODE","COMMON_VUL")=="PURE_SCAN":
            prompt = PromptAssembler.assemble_prompt_pure(code_to_be_tested)
        elif os.getenv("SCAN_MODE","COMMON_VUL")=="SPECIFIC_PROJECT":
            business_type = task.recommendation
            business_type_list = business_type.split(',')
            prompt = PromptAssembler.assemble_prompt_for_specific_project(code_to_be_tested, business_type_list)

        # 如果有历史对话，添加到prompt中
        if dialogue_history:
            history_text = "\n\nPreviously Found Vulnerabilities:\n" + "\n".join(dialogue_history)
            prompt += history_text + "\n\nExcluding these vulnerabilities, please continue searching for other potential vulnerabilities."
        
        print(f"\n📝 基础提示词长度: {len(prompt)} 字符")
        
        # 发送请求并获取响应
        response_vul = ask_claude(prompt)
        print(f"\n✨ 本轮响应长度: {len(response_vul)} 字符")
        
        # 保存对话历史
        if response_vul:
            self.dialogue_history.add_response(task.name, current_index, response_vul)
            print(f"✅ 已保存对话历史，当前历史总数: {len(self.dialogue_history.get_history(task.name, current_index))}")
        
        response_vul = response_vul if response_vul is not None else "no"                
        self.project_taskmgr.update_result(task.id, response_vul, "","")
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    pass