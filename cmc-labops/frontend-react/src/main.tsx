import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
// 全局样式与 CMAB MDM Portal 一致(字体栈/底色/滚动条/表单错误高亮)
import "./global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
