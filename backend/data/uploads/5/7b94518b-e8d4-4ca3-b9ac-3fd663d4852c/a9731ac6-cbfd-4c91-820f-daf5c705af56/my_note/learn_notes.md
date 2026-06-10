# 2026-05-20

## hw0b

### 声明数组

```java
// 方式1：类型[] 变量名
int[] arr;

// 方式2：类型 变量名[]（C风格）
int arr[];
```

## 创建数组

```java
// 指定长度
int[] arr = new int[5];

// 直接初始化
int[] arr = {1, 2, 3, 4, 5};

// 匿名数组
new int[]{1, 2, 3}
```

## 二维数组

```java
int[][] matrix = new int[3][4];
int[][] matrix = {{1,2}, {3,4}, {5,6}};
```

## 常用操作

```java
arr.length      // 获取长度
arr[i]          // 访问元素（下标从0开始）
arr[i] = value; // 赋值
```

## 示例

```java
int[] scores = new int[3];
scores[0] = 95;
scores[1] = 87;

String[] names = {"Alice", "Bob", "Charlie"};

for (int i = 0; i < names.length; i++) {
    System.out.println(names[i]);
}

// 增强for循环
for (String name : names) {
    System.out.println(name);
}
```


# 2026-05-21

### 一、类型系统与变量
- **静态类型**：所有变量在编译时确定类型，必须显式声明。
- **基本类型（小写）**：`int`、`double`、`boolean`、`char` 等。
- **引用类型（大写开头）**：如 `String`，以及所有类类型。
- **基本类型 vs 包装类**：每个基本类型都有对应的引用类型（`Integer`、`Double`、`Boolean`、`Character`），在泛型中必须使用包装类。两者间通常可以自动装箱/拆箱。
- **null 值**：
  - 类似 Python 的 `None`，只能赋值给引用类型。
  - 对 `null` 访问成员或方法会抛出 `NullPointerException`。

---

### 二、数组（固定大小）
- **声明与初始化**：
  - `int[] arr = new int[3];` → 元素为默认值（`int` 默认为 0）。
  - `int[] arr = {4, 7, 10};` → 直接初始化。
- **访问**：`arr[0]` 读写，**不支持负索引和切片**。
- **长度**：`arr.length`（成员变量，无括号）。
- **打印**：需借助 `Arrays.toString(arr)`。
- **遍历**：可用传统 `for` 循环或增强 `for` 循环。

---

### 三、集合框架（核心数据结构）
Java 的集合框架以接口和实现类的方式组织，常用的有三种：

#### 1. List（可调整大小，有序可重复）
- **接口**：`List<E>`，常用实现 `ArrayList<>`。
- **声明**：`List<String> lst = new ArrayList<>();`
- **常用方法**：
  - `add(element)`、`set(index, element)`、`get(index)`
  - `size()`、`contains(element)`
- **不支持切片和负索引**。

#### 2. Set（不可重复）
- **接口**：`Set<E>`，实现：`HashSet`（无序，速度快）、`TreeSet`（自然排序或定制排序）。
- **声明**：`Set<Integer> set = new HashSet<>();`
- **常用方法**：`add`、`remove`、`size`、`contains`。
- **特点**：添加重复元素无效果。

#### 3. Map（键值对）
- **接口**：`Map<K, V>`，实现：`HashMap`（无序）、`TreeMap`（按键排序）。
- **声明**：`Map<String, String> map = new HashMap<>();`
- **常用方法**：
  - `put(key, value)`（重复键会覆盖旧值）、`get(key)`
  - `size()`、`containsKey(key)`
- **遍历**：通常通过 `keySet()` 遍历键，再用 `get` 取值；或使用 `entrySet()` 同时获取键和值。
- **增强 for 循环不能直接用于 Map**，需对集合视图使用。

---

### 四、增强型 for 循环（for-each）
- **语法**：`for (类型 临时变量 : 数组或Iterable对象) { ... }`
- 示例：
  - 数组：`for (int i : array)`
  - List/Set：`for (String elem : lst)`
- **注意**：声明变量类型，用 `:` 而非 `in`。

---

### 五、类与对象基础
- **类定义**：`public class 类名 { ... }`
- **实例变量**：通常在类中直接声明（示例中用 `public int x;`，实际中多用封装）。
- **构造方法**：
  - 方法名与类名相同，无返回值。
  - 用 `this.变量名` 区分实例变量和参数。
  - 可重载，一个构造器可用 `this(参数)` 调用另一个构造器。
- **实例方法**：不需 `static`，可访问实例变量。
- **创建对象**：必须用 `new` 关键字，如 `Point p1 = new Point(5, 9);`
- **引用与 Python 的区别**：Java 中 `p1` 是引用，通过引用操作对象。

---

### 六、程序入口与 main 方法
- **方法签名**：`public static void main(String[] args)`
- **位置**：必须定义在某个类内部。
- **作用**：程序的执行起点，可调用类内其他方法或创建对象。
- **运行**：IDE（如 IntelliJ）会在 `main` 方法旁显示绿色播放按钮，点击即可运行。

---

### 七、异常处理
- **抛出异常**：`throw new Exception("错误信息");`
- **使用场景**：如方法参数校验失败时抛出。
- **对比 Python**：类似 `raise Exception("...")`。
- Java 的异常体系更复杂（受检异常与非受检异常），此处只是入门用法。

---

### 模块间关系
- **类型系统**是一切的基础，决定了变量如何声明。
- **数组与集合**是数据容器的两种形态，数组定长、性能高，集合灵活、功能丰富。
- **增强 for 循环**是遍历数组和集合的统一简洁方式。
- **类与对象**实现了自定义数据和行为，所有 Java 程序都基于类构建。
- **main 方法**将各个部分串联成可执行程序，异常保证程序的健壮性。
