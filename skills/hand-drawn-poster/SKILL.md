---
name: hand-drawn-poster
description: Renders hand-drawn (sketch/notebook style) poster and infographic PNGs by typesetting content in HTML/CSS and screenshotting with headless Chrome, then visually verifying the result. Use when the user asks for 手绘图/手绘风图片, hand-drawn style image, sketch poster, notebook-style infographic, a one-page visual summary, or wants text-heavy content (checklists, plans, cheat sheets) turned into a shareable image. Preferred over AI image generation whenever the image must contain accurate text, especially Chinese text.
---

# 手绘风海报生成（HTML/CSS → PNG）

核心原理：**文字排版交给浏览器（100% 准确，AI 生图会糊中文），"手绘感"用几条 CSS 技巧伪造，最后无头 Chrome 截图成 PNG 并读图验收**。

## 工作流程

```
- [ ] 1. 写单页 HTML（固定宽度 1240px，用 template.html 的配方）
- [ ] 2. 无头 Chrome 截图（scripts/render.sh，2x 高清）
- [ ] 3. 用 Read 工具看生成的 PNG，检查：裁切/空白/emoji 方框/字体降级
- [ ] 4. 迭代高度直到构图完整，复制成品到目标路径并告知用户
```

**第 1 步**：把内容组织成卡片区块（标题、数字气泡、带标签的卡片、轮换表格、底部要点），写入 `/tmp/<主题名>/poster.html`。直接复制 [template.html](template.html) 改内容，不要从零写 CSS。

**第 2 步**：

```bash
bash scripts/render.sh /tmp/<主题名>/poster.html /tmp/<主题名>/poster.png auto
```

高度优先用 `auto`（脚本会先测量页面 `data-content-height` 再截图，页面须带 template.html 末尾的自测量脚本）。测量失败时回退 2400，宁可留白也别裁切，再手动迭代。

**第 3 步（必做）**：用 Read 工具读 PNG 自查。常见问题：
- 底部大片空白 → 减小高度重截（内容底边 + ~50px 留白）
- 内容被裁掉 → 增大高度
- 某字符显示成 □（tofu）→ 换成稳妥符号
- 字体不是手写体 → 检查 font-family 降级链

**第 4 步**：`cp` 成品到用户可见路径（工作区或桌面），报告文件位置和尺寸。

## 手绘感 CSS 配方（关键，全部在 template.html 里）

1. **手写字体**（贡献 70% 手绘感）：
   `font-family:'Hanzipen SC','Kaiti SC','STKaiti','BiauKai','PingFang SC',cursive;`
   macOS 自带手札体/楷体。非 macOS 可引 Google Fonts 的 `Ma Shan Zheng`（网络可达时）。
2. **歪扭边框**（经典 hack，不对称圆角让直线变弧）：
   `border:3px solid #2b2b2b; border-radius:255px 15px 225px 15px / 15px 225px 15px 255px;`
   配合零模糊实心阴影 `box-shadow:3px 4px 0 rgba(43,43,43,.18)` 模拟第二道墨迹。
3. **荧光笔划线**：`background:linear-gradient(transparent 58%, #ffe066 58%)`——只涂文字下半截。
4. **微旋转**：卡片/标签/标题各 `rotate(-2deg~1deg)`，打破"太直太齐"的机器感。
5. **纸张背景**：米黄底 `#fbf5e6` + 点格纹理
   `background:radial-gradient(#e9dfc8 1px, transparent 1.5px); background-size:26px 26px;`
6. **表格线用虚线**：`border-bottom:3px dashed` / `2px dotted`，像铅笔分隔线。
7. 彩色小标签（`position:absolute; top:-14px` 骑在卡片边框上）区分区块。

## 渲染命令要点

- `--headless=new --screenshot`：截图输出
- `--force-device-scale-factor=2`：2 倍分辨率，手机放大不糊
- `--virtual-time-budget=5000`：等字体加载完再截，否则可能截到降级字体
- `--window-size=W,H`：窗口固定，H 即第 2/3 步迭代的参数
- `--hide-scrollbars`：隐藏滚动条

## 坑清单

- **emoji 不稳定**：🍽 这类符号常渲染成方框。稳妥选择：✦ ⚠️ 📌 ⚖️  🥪 🍌 ●；不确定的项改用彩色圆点 `●` + CSS 颜色。
- **别用 AI 生图模型**做含文字的图：中文必糊，且无法精确修改。
- **宽度固定 1240px**：内容高度随文字变化，只有高度需要迭代。
- **改内容只改 HTML 文本**，CSS 配方原样保留，风格即稳定复现。

## 文件

- [template.html](template.html)：完整 CSS 配方 + 组件骨架（标题/数字气泡/卡片/轮换表/红框提示/底线列表），复制后替换文案。
- [scripts/render.sh](scripts/render.sh)：渲染脚本（自动定位 Chrome，2x 输出，打印尺寸）。