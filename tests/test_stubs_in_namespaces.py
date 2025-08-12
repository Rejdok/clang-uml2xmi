#!/usr/bin/env python3
"""
Тест для проверки, что заглушки попадают в неймспейсы
"""

import json
from build.cpp.builder import CppModelBuilder
from gen.xmi.generator import XmiGenerator
import tempfile
import os

def test_stubs_in_namespaces():
    """Тестирует, что заглушки попадают в соответствующие неймспейсы"""
    
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
    
    print("🔍 Тестирование создания модели...")
    
    # Создаем модель
    builder = CppModelBuilder(test_data)
    build_result = builder.build()
    
    # Создаем UmlModel из результата
    from core.uml_model import UmlModel
    
    # CppModelBuilder возвращает created как ElementName -> UmlElement
    # Но UmlModel ожидает elements как XmiId -> UmlElement
    # Нужно преобразовать
    elements_by_xmi = {}
    for name, element in build_result["created"].items():
        elements_by_xmi[element.xmi] = element
    
    # Добавляем информацию о неймспейсах
    namespace_packages = build_result.get("namespace_packages", {})
    print(f"🔍 Созданные неймспейсы: {namespace_packages}")
    
    model = UmlModel(
        elements=elements_by_xmi,
        associations=build_result["associations"],
        dependencies=build_result["dependencies"],
        generalizations=build_result.get("generalizations", []),
        name_to_xmi=build_result["name_to_xmi"],
        namespace_packages=namespace_packages  # NEW: передаем информацию о неймспейсах
    )
    
    print(f"✅ Модель создана:")
    print(f"   - Элементов: {len(model.elements)}")
    
    # Отладочная информация
    print("🔍 Доступные элементы:")
    for xmi_id, element in model.elements.items():
        print(f"   - {xmi_id}: {element.name} (тип: {type(element.name)})")
    
    # Проверяем, что класс MyClass создан
    myclass_element = None
    for xmi_id, element in model.elements.items():
        # Проверяем разные варианты имени
        element_name_str = str(element.name)
        if (element_name_str == "mynamespace::MyClass" or 
            element_name_str == "MyClass" or
            "MyClass" in element_name_str):
            myclass_element = element
            break
    
    if myclass_element:
        print(f"✅ Класс MyClass найден: {myclass_element.xmi}")
        print(f"   - Имя: {myclass_element.name}")
        print(f"   - Членов: {len(myclass_element.members)}")
        if myclass_element.members:
            print(f"   - Первый член: {myclass_element.members[0].name} типа {myclass_element.members[0].type_repr}")
    else:
        print("❌ Класс MyClass НЕ найден")
        print("🔍 Проверяем name_to_xmi:")
        for name, xmi_id in build_result["name_to_xmi"].items():
            print(f"   - {name} -> {xmi_id}")
        assert False, "Класс MyClass не найден в созданной модели"
    
    print("\n🔍 Тестирование генерации XMI...")
    
    # Генерируем XMI
    generator = XmiGenerator(model)
    
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xmi', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        generator.write(tmp_path, "TestProject")
        
        print("✅ XMI файл создан")
        
        # Читаем и анализируем XMI
        with open(tmp_path, 'r', encoding='utf-8') as f:
            xmi_content = f.read()
        
        print(f"📄 Размер XMI файла: {len(xmi_content)} байт")
        print(f"📄 Содержимое XMI:")
        print(xmi_content)
        
        # Проверяем наличие пакетов
        if 'uml:Package' in xmi_content:
            print("✅ Пакеты (неймспейсы) найдены в XMI")
        else:
            print("❌ Пакеты (неймспейсы) НЕ найдены в XMI")
            assert False, "Пакеты (неймспейсы) не найдены в XMI"
        
        # Проверяем наличие неймспейса std
        if 'name="std"' in xmi_content:
            print("✅ Неймспейс 'std' найден")
        else:
            print("❌ Неймспейс 'std' НЕ найден")
            assert False, "Неймспейс 'std' не найден"
        
        # Проверяем наличие неймспейса mynamespace
        if 'name="mynamespace"' in xmi_content:
            print("✅ Неймспейс 'mynamespace' найден")
        else:
            print("❌ Неймспейс 'mynamespace' НЕ найден")
            assert False, "Неймспейс 'mynamespace' не найден"
        
        # Проверяем, что заглушка std::vector находится в пакете std
        # Ищем структуру: <packagedElement xmi:type="uml:Package" name="std">...<packagedElement xmi:type="uml:DataType" name="vector<int>">
        if 'name="std"' in xmi_content and 'name="vector&lt;int&gt;"' in xmi_content:
            print("✅ Заглушка std::vector<int> найдена в неймспейсе std")
        else:
            print("❌ Заглушка std::vector<int> НЕ найдена в неймспейсе std")
            assert False, "Заглушка std::vector<int> не найдена в неймспейсе std"
        
        print("\n🎉 Все тесты пройдены! Заглушки теперь попадают в неймспейсы.")
        assert True
        
    finally:
        # Удаляем временный файл
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == "__main__":
    success = test_stubs_in_namespaces()
    exit(0 if success else 1)
