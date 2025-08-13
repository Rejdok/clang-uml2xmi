## Association generation rules (user guide)

How associations are produced from your C++ code.

Goals:
- Prefer ends owned by classes when there are real fields
- Allow non-field relations via owned ends (configurable)
- Keep association names predictable and readable

### Naming
Association name is:
`<SrcFQN>::<src_prop>-><TgtFQN>::<tgt_prop>`

### Field-based association
- If a class has a field that points to another class, the association end on that side is owned by the class (uses the field’s name).
- If the other class has a matching back field, both ends are class-owned and linked as opposites.
- If the other class has no back field, the opposite end can be created as an owned end (see strictness below).

### Non-field association
For computed links, manager-provided relations, link objects, qualified associations, etc., where no real class field exists on a side:
- The missing side can be created as an owned end, and the association marked with the `OwnedEnd` stereotype indicating which sides are owned vs class.
- If both sides are non-field, both ends are owned and marked as opposites.

### Aggregation and multiplicity
- Raw/reference/pointer fields → aggregation “shared”; value members → “none”; `unique_ptr` → “composite”.
- Containers (e.g., `std::vector`) imply multiplicity “*” toward the element type. Smart pointers and other wrappers may adjust aggregation per known rules.

### Type profiles (optional)
- You can provide type profiles to customize roles and multiplicities for library types (e.g., naming ends in `std::map` as `key`/`value`).
- Pass one or more profiles via CLI if supported in your setup.

### Strictness and annotations
- `--no-owned-end`: forbid creating owned ends for non-field sides (only class fields are allowed).
- `--no-owned-end-annotation`: do not add the `OwnedEnd` stereotype when owned ends are used.


## C++ examples and how they map

Below are representative C++ snippets and what the generator produces.

### 1) Unidirectional field-based association
```cpp
namespace ns {
  struct B {};
  struct A {
    B* b; // pointer field
  };
}
```
- `A` side is class-owned (end name `b`).
- `B` side: created as owned end if allowed; otherwise not created.
- Aggregation: shared; multiplicity: 1
- Name: `ns::A::b->ns::B`

### 2) Bidirectional field-based (opposites)
```cpp
namespace ns {
  struct B { A* b; };
  struct A { B* b; };
}
```
- Both ends are class-owned; opposites are linked automatically.
- Aggregation: shared on both sides; name: `ns::A::b->ns::B::b`

### 3) Mismatched member names (fallback on one side)
```cpp
namespace ns {
  struct B { A* a; };   // name 'a'
  struct A { B* b; };   // name 'b'
}
```
- Association is formed from `A::b`. `B`’s name doesn’t match — an owned end may be created (if allowed).
- Name: `ns::A::b->ns::B`

### 4) Smart pointers and aggregation
```cpp
namespace ns {
  struct B {};
  struct A {
    std::unique_ptr<B> ub;   // composite
    std::shared_ptr<B> sb;   // shared
  };
}
```
- `unique_ptr` → aggregation “composite”; `shared_ptr` → “shared”
- Multiplicity: 1; Names: `ns::A::ub->ns::B`, `ns::A::sb->ns::B`

### 5) Containers and multiplicity
```cpp
namespace ns {
  struct B {};
  struct A {
    std::vector<B> items;
  };
}
```
- Multiplicity toward `B` is `*`; aggregation defaults to “none” (unless overridden by a profile)
- Name: `ns::A::items->ns::B`

With templates and profiles (if enabled) element roles can be named per-argument:
```cpp
namespace ns {
  struct A { std::map<int, B> index; };
}
```
- With a type profile, ends can be named `key`/`value`; otherwise — `index_arg0`, `index_arg1`.

### 6) Nested templates (container + smart pointer)
```cpp
namespace ns {
  struct B {};
  struct A {
    std::vector<std::unique_ptr<B>> pool;
  };
}
```
- Multiplicity: `*`; aggregation: “composite”; name: `ns::A::pool->ns::B`

### 7) Link object (association class pattern)
```cpp
namespace ns {
  struct A {}; struct B {};
  struct Link { A* a; B* b; };
}
```
- `A`/`B` have no fields; the relation is expressed via `Link`.
- The generator creates an `A`–`B` association with owned ends on both sides and `OwnedEnd` mark. `Link` remains a regular class.

### 8) Manager-provided relation (non-field)
```cpp
namespace ns {
  struct User { /* no direct field */ };
  struct Group { /* no direct field */ };
  struct Registry {
    static std::vector<Group*> groupsOf(const User&);
  };
}
```
- No class fields; the relation is computed. The generator creates a non-field association with owned ends (if allowed by strictness flags).

### 9) Computed property via getter only
```cpp
namespace ns {
  struct B {};
  struct A {
    const B& getB() const; // no backing field
  };
}
```
- Treated as non-field; see (8).

### 10) Qualified associations (logical key/value roles)
```cpp
namespace ns {
  struct Key{}; struct Value{};
  struct Store { std::unordered_map<Key, Value> kv; };
}
```
- With a type profile — ends `key`/`value`; without a profile — generic names.

### 11) Bidirectional value members
```cpp
namespace ns {
  struct B { A a; };
  struct A { B b; };
}
```
- Value members are possible; aggregation defaults to “none”.
- Both ends are class-owned; opposites are linked when names match (see 3 for mismatches).

### 12) CLI flags
```bash
python cpp2uml.py model.json out.uml out.notation --pretty --no-owned-end --no-owned-end-annotation
```
- `--no-owned-end`: disable owned ends (only class fields are used)
- `--no-owned-end-annotation`: do not add the `OwnedEnd` mark


