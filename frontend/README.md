# 快递企业智能客服 · 前端

Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router + Axios。

## 快速开始

```bash
cd frontend
npm install       # 安装依赖（若安装了 pnpm 也可用 pnpm install）
npm run dev       # 启动开发服务器 http://localhost:5173
```

开发环境由 Vite 将 `/api` 代理到后端 `http://localhost:8000`，无需处理跨域。

## 目录结构

```
frontend/
├── vite.config.ts        # Vite 配置 + @ 别名 + /api 代理
├── tsconfig.json         # TypeScript 配置
└── src/
    ├── main.ts           # 入口：挂载 Pinia / Router / Element Plus
    ├── App.vue           # 根组件
    ├── api/              # Axios 封装（http.ts 拦截器）+ 接口模块
    ├── router/           # Vue Router
    ├── stores/           # Pinia
    ├── layouts/          # 布局（默认布局，后续按三端拆分）
    ├── views/            # 页面视图
    └── styles/           # 设计令牌 tokens.scss + 全局样式
```

## 常用命令

```bash
npm run dev          # 开发
npm run build        # 构建
npm run type-check   # 类型检查
```
