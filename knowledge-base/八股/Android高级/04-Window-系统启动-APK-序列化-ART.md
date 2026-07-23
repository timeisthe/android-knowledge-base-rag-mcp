---
category: 八股
created_at: '2026-07-23'
difficulty: advanced
source_file: Android高级开发面试八股优化整理.md
subcategory: Android高级
tags:
- Window
- ViewRootImpl
- AMS
- ATMS
- Zygote
- APK
- 签名
- Parcelable
- ART
title: Android 高级八股：Window、系统启动、APK、序列化与 ART
updated_at: '2026-07-23'
verified_at: '2026-07-23'
---

# Android 高级八股：Window、系统启动、APK、序列化与 ART

> 时效性：2026-07-23 使用 Android CLI 1.0.15857036 与 Android 官方知识库复核。版本敏感内容已在正文标注；第三方旧链接仅作历史索引。

## 16. Window、DecorView 与 ViewRootImpl

Activity 并不直接显示 View。Activity 持有 Window，通常实现是 PhoneWindow；PhoneWindow 内部有 DecorView；DecorView 通过 WindowManager 添加到窗口；ViewRootImpl 连接 View 树和 WindowManagerService，负责输入事件、绘制调度、Surface 协作。

关系：

```text
Activity
-> PhoneWindow
-> DecorView
-> WindowManager.addView
-> ViewRootImpl
-> WMS / SurfaceFlinger
```

`setContentView` 本质是把业务布局添加到 DecorView 的 content 区域。

### 16.1 Window 与 WindowManager 补充题

**Window 是什么？**

Window 是抽象窗口概念，Android 中常见实现是 PhoneWindow。它负责管理 DecorView、窗口属性、输入和与 WindowManager 的交互。

**WindowManager 是什么？**

WindowManager 是应用侧操作窗口的入口，常用 `addView/removeView/updateViewLayout`。真正的窗口管理在 system_server 的 WindowManagerService 中。

**DecorView 什么时候添加到 Window？**

一般在 ActivityThread 执行 `handleResumeActivity` 时，通过 WindowManager 把 DecorView 添加到窗口。`setContentView` 只是准备 View 树，不等于已经显示。

## 17. AMS、Zygote 与系统启动

### 17.1 系统启动简化流程

1. Bootloader 启动 Linux Kernel。
2. Kernel 启动 init 进程。
3. init 解析 rc 文件，启动 Zygote。
4. Zygote 预加载类和资源，等待 fork 请求。
5. Zygote fork SystemServer。
6. SystemServer 启动 AMS/ATMS、PMS、WMS 等系统服务。
7. 系统启动 Launcher。

### 17.2 为什么应用进程由 Zygote fork

Zygote 预加载了大量通用类和资源，fork 后子进程可以通过 Copy-On-Write 共享内存，提升应用启动速度并减少内存占用。SystemServer 负责管理服务，不直接 fork 普通应用进程，可以降低复杂度和风险。

### 17.3 Zygote 为什么用 socket 而不是 Binder

Zygote 启动早于大部分 Binder 服务，且 fork 多线程进程有风险。Zygote 保持相对简单的单线程 socket 请求处理模型，更适合安全地 fork 子进程。

### 17.4 AMS / ActivityThread 补充题

**ActivityThread 是线程吗？**

ActivityThread 不是 Thread 子类，而是应用主线程的管理类。它运行在主线程中，负责组件调度、生命周期、资源、Provider 安装等。

**ApplicationThread 是什么？**

ApplicationThread 是 ActivityThread 的内部 Binder 对象，是 system_server 回调应用进程的入口。AMS/ATMS 通过它通知应用启动 Activity、创建 Service、分发 Receiver 等。

**Instrumentation 有什么作用？**

Instrumentation 负责创建组件、调用生命周期，也可用于测试和 Hook。Activity 的启动、生命周期回调最终会经过 Instrumentation 的相关方法。

**ActivityManager、ActivityManagerService、ActivityTaskManagerService 区别？**

ActivityManager 是应用侧 API 门面；AMS 是 system_server 中管理进程、服务、广播等的重要系统服务；Android 10 左右 Activity/任务相关职责拆到了 ATMS。面试回答时可以说“老版本常统称 AMS，新版本 Activity 栈管理更多在 ATMS”。

## 18. APK 打包、安装与签名

### 18.1 APK 组成

APK 主要包含：`classes.dex`、resources.arsc、res 资源、assets、lib so、AndroidManifest.xml、META-INF/签名块等。

### 18.2 打包流程

简化流程：

1. AAPT2 编译资源，生成资源表和 R 文件。
2. Kotlin/Java 编译成 class。
3. D8/R8 转 dex，并做压缩、混淆、优化。
4. 打包资源、dex、so、assets。
5. zipalign 对齐。
6. apksigner 签名。

### 18.3 签名机制

- v1：JAR 签名，校验单个条目，兼容老系统。
- v2：对整个 APK 签名块校验，速度更快，能发现更多篡改。
- v3/v4：支持密钥轮换、增量安装等能力。

### 18.4 系统启动、应用启动、安装打包补充题

**冷启动、温启动、热启动区别？**

冷启动是进程不存在，需要创建进程、Application、首个 Activity；温启动通常进程还在但 Activity 需重建；热启动是 Activity/任务仍在内存中，回前台成本最低。优化重点主要在冷启动。

**APK 安装流程大致是什么？**

PackageInstaller 交给 PMS 处理，PMS 解析 APK、校验签名、扫描 Manifest、提取/优化 dex、拷贝文件、写入包信息、分配 uid、注册四大组件，最后发送安装完成广播。

**v1/v2 签名区别？**

v1 是 JAR 条目级签名，兼容老系统但校验慢且覆盖范围有限；v2 对 APK 签名块做整体校验，速度更快，也能发现更多篡改。新包通常同时启用多版本签名以兼容不同系统。

## 19. 序列化、Parcelable 与 Bundle

`Parcel` 是为 Android IPC/系统状态传输设计的高性能容器，不是通用持久化格式。Intent 与 SavedState 中优先放系统已知的基本类型；复杂 Kotlin 类型使用 `@Parcelize` 生成 Parcelable。

`Serializable` 使用方便但成本和版本兼容风险更高；`serialVersionUID` 只能参与类版本兼容判断，不能解决任意字段变化。

跨应用/跨版本 IPC 应谨慎传自定义 Parcelable：双方必须拥有兼容的同版本类定义，系统中间层还可能修改 Bundle。更稳定的边界是基本类型、稳定 AIDL 数据结构、文件描述符或 Uri。

Binder 事务缓冲区当前约 1MB，按进程共享。大对象、Bitmap、长列表不要塞进 Intent、SavedStateHandle 或 `rememberSaveable`；传 ID、Uri、文件描述符或从数据库重新加载。

## 20. ART、Dalvik 与运行时

Dalvik 是早期 Android 虚拟机，主要使用解释执行 + JIT。ART 从 Android 5.0 成为默认运行时，结合 AOT、JIT、Profile Guided Compilation，实现安装、运行和热点代码优化之间的平衡。

不要再简单说“ART 只 AOT、Dalvik 只 JIT”。现代 ART 同时使用解释器、JIT、AOT 和 Profile。

## 当前官方参考

- [Parcelable and Bundle](https://developer.android.com/guide/components/activities/parcelables-and-bundles)
- [Parcelize](https://developer.android.com/kotlin/parcelize)
- [Platform architecture](https://developer.android.com/guide/platform)
