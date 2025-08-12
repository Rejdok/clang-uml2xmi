#!/usr/bin/env python3
"""
Отладка namespace tree в XmiGenerator
"""

import json
from build.cpp.builder import CppModelBuilder
from XmiGenerator import XmiGenerator
from UmlModel import UmlModel

def debug_namespace_tree():
    """Отлаживает создание namespace tree"""
    
    # Тестовые данные с неймспейсами
    test_data = {
        "elements": [
            {
                "id": "class_1",
                "name": "MyClass",
                "qualified_name": "mynamespace::MyClass",
                "type": "class",
                "display_name": "MyClass",
                "is_abstract": False,
                "members": [
                    {
                        "name": "data",
                        "type": "std::vector<int>",
                        "visibility": "private",
                        "is_static": False
                    }
                ],
                "operations": []
            }
        ]
    }
    
    print("🔍 Создание модели...")
    
    # Создаем модель
    builder = CppModelBuilder(test_data)
    build_result = builder.build()
    
    # Fix: The CppModelBuilder returns 'created' as ElementName->UmlElement
    # but UmlModel expects 'elements' as XmiId->UmlElement
    # We need to create the correct mapping
    elements_by_xmi = {}
    for name, element in build_result["created"].items():
        elements_by_xmi[element.xmi] = element
    
    # Создаем UmlModel из результата
    model = UmlModel(
        elements=elements_by_xmi,  # Now this is XmiId -> UmlElement
        associations=build_result["associations"],
        dependencies=build_result["dependencies"],
        generalizations=build_result.get("generalizations", []),
        name_to_xmi=build_result["name_to_xmi"],
        namespace_packages=build_result.get("namespace_packages", {})
    )
    
    print(f"✅ Модель создана:")
    print(f"   - Элементов: {len(model.elements)}")
    print(f"   - name_to_xmi: {len(model.name_to_xmi)}")
    
    # Выводим элементы
    for xmi_id, element in model.elements.items():
        print(f"   - {element.xmi}: {element.name} (kind: {element.kind.name})")
    
    # Выводим name_to_xmi
    for name, xmi_id in model.name_to_xmi.items():
        print(f"   - {name} -> {xmi_id}")
    
    print("\n🔍 Создание XmiGenerator...")
    
    # Debug: Check the mapping before creating XmiGenerator
    print("🔍 Debug: Checking element mapping...")
    print(f"   - model.elements keys: {list(model.elements.keys())}")
    print(f"   - model.name_to_xmi values: {list(model.name_to_xmi.values())}")
    
    # Check if the mapping should work
    for name, xmi_id in model.name_to_xmi.items():
        if xmi_id in model.elements:
            print(f"   ✓ {name} -> {xmi_id} found in elements")
        else:
            print(f"   ✗ {name} -> {xmi_id} NOT found in elements")
    
    # Создаем XmiGenerator
    generator = XmiGenerator(model)
    
    print(f"✅ XmiGenerator создан:")
    print(f"   - created: {len(generator.created)}")
    print(f"   - namespace_tree: {len(generator.namespace_tree)}")
    
    # Выводим created
    print("\n📋 created (ElementName -> UmlElement):")
    for name, element in generator.created.items():
        print(f"   - {name} -> {element.xmi} ({element.kind.name})")
    
    # Выводим namespace_tree
    print("\n🌳 namespace_tree:")
    def print_tree(tree, indent=0):
        for name, item in tree.items():
            if isinstance(item, dict) and item.get('__namespace__'):
                print("  " * indent + f"📁 {name} (namespace)")
                children = item.get('__children__', {})
                print_tree(children, indent + 1)
            else:
                if hasattr(item, 'kind'):
                    print("  " * indent + f"📄 {name} ({item.kind.name})")
                else:
                    print("  " * indent + f"❓ {name} (unknown)")
    
    print_tree(generator.namespace_tree)
    
    # Проверяем, что происходит в _write_package_contents
    print("\n🔍 Тестирование _write_package_contents...")
    
    # Создаем mock visitor для тестирования
    class MockVisitor:
        def __init__(self):
            self.packages_created = []
            self.elements_written = []
        
        def writer(self):
            class MockWriter:
                def start_package(self, package_id, name):
                    print(f"   📁 start_package({package_id}, {name})")
                
                def end_package(self):
                    print(f"   📁 end_package()")
                
                def start_packaged_element(self, xmi, element_type, name, **kwargs):
                    print(f"   📄 start_packaged_element({xmi}, {element_type}, {name})")
                
                def end_packaged_element(self):
                    print(f"   📄 end_packaged_element()")
            
            return MockWriter()
    
    mock_visitor = MockVisitor()
    
    print("Вызов _write_package_contents:")
    generator._write_package_contents(mock_visitor, generator.namespace_tree)

if __name__ == "__main__":
    debug_namespace_tree()
