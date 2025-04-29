import json
import os
import re
import numpy as np
import requests
from openai import OpenAI
import time

class JSONExtractError(Exception):
    def __init__(self, ErrorInfo):
        super().__init__(self)
        self.errorinfo=ErrorInfo
    def __str__(self):
        return self.errorinfo

def azure_openai(prompt):
    # Azure OpenAI配置
    api_key = os.environ.get('AZURE_API_KEY')
    api_base = os.environ.get('AZURE_API_BASE')
    api_version = os.environ.get('AZURE_API_VERSION')
    deployment_name = os.environ.get('AZURE_DEPLOYMENT_NAME')
    # 构建URL
    url = f"{api_base}openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"
    # 设置请求头
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    # 设置请求体
    data = {
        "messages": [
            {"role": "system", "content": "你是一个熟悉智能合约与区块链安全的安全专家。"},
            {"role": "user", "content": prompt}
        ],
        # "max_tokens": 150
    }
    try:
        # 发送POST请求
        response = requests.post(url, headers=headers, json=data)
        # 检查响应状态
        response.raise_for_status()
        # 解析JSON响应
        result = response.json()
        # 打印响应
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print("Azure OpenAI测试失败。错误:", str(e))
        return None
    

def azure_openai_json(prompt):
    # Azure OpenAI配置
    api_key = os.environ.get('AZURE_API_KEY')
    api_base = os.environ.get('AZURE_API_BASE')
    api_version = os.environ.get('AZURE_API_VERSION')
    deployment_name = os.environ.get('AZURE_DEPLOYMENT_NAME')
    # 构建URL
    url = f"{api_base}openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"
    # 设置请求头
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    # 设置请求体
    data = {
        "response_format": { "type": "json_object" },
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant designed to output JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    try:
        # 发送POST请求
        response = requests.post(url, headers=headers, json=data)
        # 检查响应状态
        response.raise_for_status()
        # 解析JSON响应
        result = response.json()
        # 打印响应
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print("Azure OpenAI测试失败。错误:", str(e))
        return None

    
def ask_openai_common(prompt):
        api_base = os.environ.get('OPENAI_API_BASE', 'api.openai.com')  # Replace with your actual OpenAI API base URL
        api_key = os.environ.get('OPENAI_API_KEY')  # Replace with your actual OpenAI API key
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": os.environ.get('OPENAI_MODEL'),  # Replace with your actual OpenAI model
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        response = requests.post(f'https://{api_base}/chat/completions', headers=headers, json=data)
        try:
            response_josn = response.json()
        except Exception as e:
            return ''
        if 'choices' not in response_josn:
            return ''
        return response_josn['choices'][0]['message']['content']
def ask_openai_for_json(prompt):
    api_base = os.environ.get('OPENAI_API_BASE', 'api.openai.com')  # Replace with your actual OpenAI API base URL
    api_key = os.environ.get('OPENAI_API_KEY')  # Replace with your actual OpenAI API key
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": os.environ.get('OPENAI_MODEL'),
        "response_format": { "type": "json_object" },
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant designed to output JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    while True:
        try:
            response = requests.post(f'https://{api_base}/chat/completions', headers=headers, json=data)
            print("Raw response text:", response.text)
            response_json = response.json()
            if 'choices' not in response_json:
                return ''
            response_content = response_json['choices'][0]['message']['content']
            if "```json" in response_content:
                try:
                    cleaned_json = extract_json_string(response_content)
                    break
                except JSONExtractError as e:
                    print(e)
                    print("===Error in extracting json. Retry request===")
                    continue
            else:
                try:
                    decoded_content = json.loads(response_content)
                    if isinstance(decoded_content, dict):
                        cleaned_json = response_content
                        break
                    else:
                        print("===Unexpected JSON format. Retry request===")
                        print(response_content)
                        continue
                except json.JSONDecodeError as e:
                    print("===Error in decoding JSON. Retry request===")
                    continue
                except Exception as e:
                    print(f"===Error in requesting LLM. Retry request===\n{e}")
                    if 'response' in locals():
                        print("Response content:", response.text)
                    continue
        except Exception as e:
            print(f"===Error in requesting LLM. Retry request===\n{e}")
    return cleaned_json

def extract_json_string(response):
    json_pattern = re.compile(r'```json(.*?)```', re.DOTALL)
    response = response.strip()
    extracted_json = re.findall(json_pattern, response)
    if len(extracted_json) > 1:
        print("[DEBUG]⚠️Error json string:")
        print(response)
        raise JSONExtractError("⚠️Return JSON format error: More than one JSON format found")
    elif len(extracted_json) == 0:
        print("[DEBUG]⚠️Error json string:")
        print(response)
        raise JSONExtractError("⚠️Return JSON format error: No JSON format found")
    else:
        cleaned_json = extracted_json[0]
        data_json = json.loads(cleaned_json)
        if isinstance(data_json, dict):
            return cleaned_json
        else:
            print("[DEBUG]⚠️Error json string:")
            print(response)
            raise JSONExtractError("⚠️Return JSON format error: input format is not a JSON")

def common_ask_for_json(prompt):
    if os.environ.get('AZURE_OR_OPENAI') == 'AZURE':
        return azure_openai_json(prompt)
    else:
        return ask_openai_for_json(prompt)

def ask_claude(prompt):
    model = os.environ.get('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')
    api_key = os.environ.get('OPENAI_API_KEY','sk-0fzQWrcTc0DASaFT7Q0V0e7c24ZyHMKYgIDpXWrry8XHQAcj')
    api_base = os.environ.get('OPENAI_API_BASE', '4.0.wokaai.com')
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    data = {
        'model': model,
        'messages': [
            {
                'role': 'user',
                'content': prompt
            }
        ]
    }

    try:
        response = requests.post(f'https://{api_base}/chat/completions', 
                               headers=headers, 
                               json=data)
        response.raise_for_status()
        response_data = response.json()
        if 'choices' in response_data and len(response_data['choices']) > 0:
            return response_data['choices'][0]['message']['content']
        else:
            return ""
    except requests.exceptions.RequestException as e:
        print(f"{api_base}调用失败。错误: {str(e)}")
        return ""
def ask_claude_37(prompt):
    model = 'claude-3-7-sonnet-20250219'
    # print("prompt:",prompt)
    api_key = os.environ.get('OPENAI_API_KEY')
    api_base = os.environ.get('OPENAI_API_BASE', '4.0.wokaai.com')
    # print("api_base:",api_base)
    # print("api_key:",api_key)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    data = {
        'model': model,
        'messages': [
            {
                'role': 'user',
                'content': prompt
            }
        ]
    }

    try:
        response = requests.post(f'https://{api_base}/chat/completions', 
                               headers=headers, 
                               json=data)
        response.raise_for_status()
        response_data = response.json()
        if 'choices' in response_data and len(response_data['choices']) > 0:
            return response_data['choices'][0]['message']['content']
        else:
            return ""
    except requests.exceptions.RequestException as e:
        print(f"{api_base}调用失败。错误: {str(e)}")
        return ""
def ask_deepseek(prompt):
    model = 'deepseek-reasoner'
    # print("prompt:",prompt)
    api_key = os.environ.get('OPENAI_API_KEY')
    api_base = os.environ.get('OPENAI_API_BASE', '4.0.wokaai.com')
    # print("api_base:",api_base)
    # print("api_key:",api_key)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    data = {
        'model': model,
        'messages': [
            {
                'role': 'user',
                'content': prompt
            }
        ]
    }

    try:
        response = requests.post(f'https://{api_base}/chat/completions', 
                               headers=headers, 
                               json=data)
        response.raise_for_status()
        response_data = response.json()
        if 'choices' in response_data and len(response_data['choices']) > 0:
            return response_data['choices'][0]['message']['content']
        else:
            return ""
    except requests.exceptions.RequestException as e:
        print(f"wokaai deepseek API调用失败。错误: {str(e)}")
        return ""
def cut_reasoning_content(input):
    if "</think>" not in input:
        print("No </think> tag found in input")
        return input
    return input.split("</think>")[1]

def ask_o3_mini_json(prompt):
    model = 'o3-mini'
    api_key = os.environ.get('OPENAI_API_KEY')
    api_base = os.environ.get('OPENAI_API_BASE', '4.0.wokaai.com')
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    data = {
        'model': model,
        'response_format': { "type": "json_object" },
        'messages': [
            {
                'role': 'system',
                'content': 'You are a helpful assistant designed to output JSON.'
            },
            {
                'role': 'user',
                'content': prompt
            }
        ]
    }

    try:
        response = requests.post(f'https://{api_base}/chat/completions', 
                               headers=headers, 
                               json=data)
        response.raise_for_status()
        response_data = response.json()
        if 'choices' in response_data and len(response_data['choices']) > 0:
            return response_data['choices'][0]['message']['content']
        else:
            return ""
    except requests.exceptions.RequestException as e:
        print(f"wokaai o3-mini API调用失败。错误: {str(e)}")
        return ""
def ask_grok3_deepsearch(prompt):
    model = 'grok-3-deepsearch'
    # print("prompt:",prompt)
    api_key = os.environ.get('OPENAI_API_KEY')
    api_base = os.environ.get('OPENAI_API_BASE', '4.0.wokaai.com')
    # print("api_base:",api_base)
    # print("api_key:",api_key)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    data = {
        'model': model,
        'messages': [
            {
                'role': 'user',
                'content': prompt
            }
        ]
    }

    try:
        response = requests.post(f'https://{api_base}/chat/completions', 
                               headers=headers, 
                               json=data)
        response.raise_for_status()
        response_data = response.json()
        if 'choices' in response_data and len(response_data['choices']) > 0:
            return response_data['choices'][0]['message']['content']
        else:
            return ""
    except requests.exceptions.RequestException as e:
        print(f"wokaai deepseek API调用失败。错误: {str(e)}")
        return ""
def ask_o3_mini(prompt):
    model = 'o3-mini'
    # print("prompt:",prompt)
    api_key = os.environ.get('OPENAI_API_KEY')
    api_base = os.environ.get('OPENAI_API_BASE', '4.0.wokaai.com')
    # print("api_base:",api_base)
    # print("api_key:",api_key)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    data = {
        'model': model,
        'messages': [
            {
                'role': 'user',
                'content': prompt
            }
        ]
    }

    try:
        response = requests.post(f'https://{api_base}/chat/completions', 
                               headers=headers, 
                               json=data)
        response.raise_for_status()
        response_data = response.json()
        if 'choices' in response_data and len(response_data['choices']) > 0:
            return response_data['choices'][0]['message']['content']
        else:
            return ""
    except requests.exceptions.RequestException as e:
        print(f"wokaai deepseek API调用失败。错误: {str(e)}")
        return ""
def common_ask(prompt):
    model_type = os.environ.get('AZURE_OR_OPENAI', 'CLAUDE')
    if model_type == 'AZURE':
        return azure_openai(prompt)
    elif model_type == 'CLAUDE':
        return ask_claude(prompt)
    elif model_type == 'DEEPSEEK':
        return ask_deepseek(prompt)
    else:
        return ask_openai_common(prompt)

def clean_text(text: str) -> str:
    return str(text).replace(" ", "").replace("\n", "").replace("\r", "")

def common_get_embedding(text: str, max_retries: int = 3, retry_delay: int = 1):
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    api_base = os.getenv('OPENAI_API_BASE', 'api.openai.com')
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    cleaned_text = clean_text(text)
    
    data = {
        "input": cleaned_text,
        "model": model,
        "encoding_format": "float"
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(f'https://{api_base}/embeddings', json=data, headers=headers)
            response.raise_for_status()
            embedding_data = response.json()
            embedding = embedding_data['data'][0]['embedding']
            
            # Ensure the embedding is exactly 3072 elements
            if len(embedding) > 3072:
                embedding = embedding[:3072]  # Truncate if too long
            elif len(embedding) < 3072:
                # Pad with zeros if too short
                embedding.extend([0.0] * (3072 - len(embedding)))
            
            return embedding
        except requests.exceptions.RequestException as e:
            print(f"Error getting embedding (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
            else:
                print("Max retries reached. Returning zero vector as fallback.")
                return list(np.zeros(3072))  # Return zero vector as fallback
        except Exception as e:
            print(f"Unexpected error getting embedding: {str(e)}")
            return list(np.zeros(3072))  # Return zero vector as fallback

def common_ask_confirmation(prompt):
    model_type = os.environ.get('CONFIRMATION_MODEL', 'DEEPSEEK')
    if model_type == 'CLAUDE':
        return ask_claude(prompt)
    elif model_type == 'DEEPSEEK':
        return ask_deepseek(prompt)
    else:
        return ask_openai_common(prompt)
