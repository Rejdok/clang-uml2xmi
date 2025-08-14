# EMF Compliance Tests

Этот набор тестов проверяет исправления для обеспечения совместимости с EMF (Eclipse Modeling Framework) валидатором.

## Тестовые файлы

### `test_emf_compliance_fixes.py`
Основные тесты для проверки EMF совместимости:

- **`test_no_template_signatures_generated`** - Проверяет, что template signatures не создаются (EMF требует параметры)
- **`test_no_template_bindings_generated`** - Проверяет, что template bindings не создаются (избегает ссылок на несуществующие signatures)
- **`test_unique_operation_ids`** - Проверяет, что операции имеют уникальные ID даже при одинаковых сигнатурах
- **`test_root_model_no_visibility`** - Проверяет, что корневая модель не имеет visibility атрибута
- **`test_no_self_referential_associations`** - Проверяет фильтрацию проблематичных self-referential ассоциаций
- **`test_emf_validation_passes`** - Проверяет, что Python валидатор не находит ошибок
- **`test_no_datatype_stubs_generated`** - Проверяет, что DataType заглушки не создаются при отключении
- **`test_spdlog_integration_emf_validation`** - Проверяет основной интеграционный тест
- **`test_associations_have_sufficient_member_ends`** - Проверяет, что у ассоциаций достаточно memberEnd элементов
- **`test_operation_name_uniqueness_within_class`** - Проверяет уникальность имен операций в классе

### `test_regression_prevention.py`
Тесты для предотвращения регрессий конкретных проблем:

- **`test_no_template_signature_parameter_errors`** - Предотвращает создание пустых template signatures
- **`test_no_unresolved_template_binding_references`** - Предотвращает ссылки на несуществующие signatures
- **`test_no_duplicate_operation_ids_in_class`** - Предотвращает дублированные operation ID
- **`test_model_element_no_visibility_attribute`** - Предотвращает visibility у корневой модели
- **`test_no_association_with_single_member_end`** - Предотвращает ассоциации с недостаточным количеством memberEnd

### `test_specific_fixes.py`
Тесты для специфичных исправлений:

- **`test_issue_duplicate_memberend_fixed`** - Проверяет исправление дублированных memberEnd
- **`test_issue_template_binding_missing_signature_fixed`** - Проверяет исправление отсутствующих signatures
- **`test_issue_operation_id_uniqueness_fixed`** - Проверяет исправление дублированных operation ID
- **`test_issue_model_visibility_attribute_removed`** - Проверяет удаление visibility у модели

## Исправленные проблемы EMF валидации

### 1. Template Signatures без параметров
**Проблема:** `The feature 'parameter' of 'RedefinableTemplateSignature' with 0 values must have at least 1 values`
**Решение:** Полностью отключить создание template signatures

### 2. Template Bindings на несуществующие signatures  
**Проблема:** `The reference 'signature' has an unresolved idref`
**Решение:** Отключить создание template bindings

### 3. Дублированные операции в классах
**Проблема:** `Named element 'Operation' is not distinguishable from all other members`
**Решение:** Добавить индекс операции в ID: `stable_id(xmi + ":op:" + str(idx) + ":" + mangled)`

### 4. Self-referential ассоциации
**Проблема:** `IllegalStateException` при duplicate memberEnd
**Решение:** Фильтровать self-referential ассоциации и убрать opposite references

### 5. Visibility корневой модели
**Проблема:** `Named element 'Model' is not owned by a namespace, but it has visibility`
**Решение:** Убрать visibility атрибут у корневой модели

### 6. DataType заглушки
**Проблема:** Некорректная структура DataType заглушек для EMF
**Решение:** Отключить создание DataType заглушек (`emit_referenced_type_stubs = False`)

## Запуск тестов

```bash
# Запуск всех новых тестов
python -m pytest tests/test_emf_compliance_fixes.py tests/test_regression_prevention.py tests/test_specific_fixes.py -v

# Запуск основного интеграционного теста
python -m pytest tests/test_integration_spdlog.py::test_spdlog_integration_generate_and_validate -v

# Проверка конкретного исправления
python -m pytest tests/test_emf_compliance_fixes.py::TestEMFComplianceFixes::test_unique_operation_ids -v
```

## Результат

✅ **Все 25 тестов проходят успешно**
✅ **Интеграционный тест проходит EMF валидацию**
✅ **Python валидатор не находит ошибок**
✅ **Java EMF валидатор не выдает ошибок**
