# 🔧 LAZARUS - AI-Powered CMS

## 🎯 چیه؟
لازاروس یه سیستم مدیریت محتوا هوش مصنوعی هست که مثل یه پردازنده کار میکنه:
- **AI = Control Unit** — تصمیم‌گیری
- **API calls = ALU** — پردازش
- **State Register = رجیسترها** — ذخیره وضعیت

## 📦 نصب
```bash
pip install lazarus-cms
```

## 🚀 شروع
```bash
lazarus
```
اولین بار wizard اجرا میشه و ازت API و مدل رو میخواد.

## 📋 قابلیت‌ها
- 🤖 چت با هوش مصنوعی
- 🔨 ساخت وبسایت با کد
- 🧠 حافظه (یادآوری مکالمات)
- 📚 Skills (مهارت‌های طراحی)
- 🔍 جستجوی مدل‌ها
- 🧪 تست مدل
- ⚙️ پنل ادمین

## 🏗️ معماری
```
User Input → needs_code? → Yes: decompose → generate → verify → save
                         → No: chat (with memory)
```

## 📁 ساختار
```
lazarus/
├── src/lazarus/
│   ├── core/          ← هسته (config, memory, user)
│   ├── modules/       ← ماژول‌ها (ai, executor, state, planner, pipeline)
│   ├── web/           ← رابط کاربری (flask, templates)
│   ├── skills.md      ← مهارت‌ها
│   └── __main__.py    ← نقطه شروع
├── docs/              ← مستندات
└── pyproject.toml
```

## 🔧 API
لازاروس از **هر API سازگار با OpenAI** استفاده میکنه:
- OpenCode Zen
- OpenAI
- Anthropic
- DeepSeek
- و هر API دیگه

## 📄 License
MIT
