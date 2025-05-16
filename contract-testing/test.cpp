#include <iostream>

class MyClass {
public:
    virtual void foo(int x) {
        std::cout << "foo called with: " << x << std::endl;
    }
    
    virtual int bar(double y) {
        return static_cast<int>(y);
    }
};

int main() {
    MyClass obj;
    obj.foo(42);
    return 0;
} 