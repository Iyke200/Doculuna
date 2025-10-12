# DocuLuna Bot - UX Flow & Messages

This document contains the complete user experience flow and message templates for the DocuLuna Bot.

## 🟢 1️⃣ START / WELCOME MESSAGE

**User Trigger:** When a user sends /start or opens the bot for the first time.

**Bot Action & Logic:**
- Check if user exists in the database
- If new user, add them with free plan and usage_today = 0
- If returning user, show welcome-back version
- Send Welcome Message

**Bot Message:**
```
👋 Hello {first_name}!

Welcome to DocuLuna Bot 🌙 — your intelligent digital assistant for all document tasks.

✨ With me, you can easily:
• 📄 Convert between PDF ↔️ Word
• 🖼️ Turn Images into PDF
• 📊 Merge or Split PDF files
• 🗜️ Compress large documents quickly

🎁 You currently have 3 free uses per day.
Upgrade to Premium for unlimited access, faster speed, and earn up to ₦500 with our referral system!

Choose an option below 👇
```

**Inline Buttons:**
- 📂 Process Document  💎 Go Premium
- 👤 My Account  ❓ Help

---

## 💎 2️⃣ PREMIUM PLANS SECTION

**User Trigger:** User taps 💎 Go Premium button.

**Bot Action & Logic:**
- Fetch available plan details (₦1000 Weekly / ₦3500 Monthly)
- Show user the premium benefits
- If user selects a plan → Generate Paystack payment link using their user_id
- Wait for confirmation (webhook or manual check)
- When payment success → update user plan = premium, plan_type = weekly/monthly, and expiry_date

**Bot Message:**
```
💎 DocuLuna Premium Plans

Unlock the full power of DocuLuna and enjoy:
🚀 Unlimited document processing
⚡ Lightning-fast conversions
💰 ₦500 referral bonuses
🎯 Priority customer support

💰 Available Plans:
• 📅 Weekly Plan — ₦1000
• 📆 Monthly Plan — ₦3500

Select your preferred plan below 👇
```

**Inline Buttons:**
- 📅 Weekly – ₦1000  📆 Monthly – ₦3500
- 🎁 Refer & Earn  ⬅️ Back

---

## 👤 3️⃣ MY ACCOUNT SECTION

**User Trigger:** User taps 👤 My Account.

**Bot Action & Logic:**
- Fetch from database: name, status, usage_today, and plan_expiry (if premium)
- Display account details and remaining quota

**Bot Message:**
```
👤 Your Account Overview

🪪 Name: {first_name}
💎 Status: {Free / Premium}
📊 Usage Today: {used_today}/3 (Free plan limit)
⏳ Plan Expires: {expiry_date if premium}

Need more daily access or faster processing?
Upgrade to Premium anytime 🚀
```

**Inline Buttons:**
- 💎 Go Premium  ⬅️ Back

---

## ❓ 4️⃣ HELP SECTION

**User Trigger:** User taps ❓ Help.

**Bot Action & Logic:**
- Send static help guide with usage instructions

**Bot Message:**
```
📖 How to Use DocuLuna

1️⃣ Send or upload a file (PDF, Word, or Image)
2️⃣ Choose what you want to do (convert, merge, split, compress)
3️⃣ Wait a few seconds while I process your file ⏳
4️⃣ Get your clean, ready-to-use document instantly!

⚙️ Free Plan: 3 uses per day
💎 Premium Plan: Unlimited + Faster + Referral Bonuses

💬 Need help or have a question?
Contact @DocuLunaSupport
```

**Inline Buttons:**
- ⬅️ Back to Menu

---

## 🚫 5️⃣ LIMIT REACHED MESSAGE

**Trigger Condition:** When user (free) tries to process after reaching 3 uses in one day.

**Bot Logic:**
- Check usage_today ≥ 3 and plan = free
- If true → block processing and show upgrade message

**Bot Message:**
```
🚫 You've reached your 3 free daily actions.

💎 Upgrade to DocuLuna Premium to enjoy:
• Unlimited document processing
• Lightning-fast speed
• ₦500 referral rewards

Tap below to upgrade 👇
```

**Inline Buttons:**
- 💎 Upgrade Now  🎁 Refer & Earn ₦500

---

## 🔁 6️⃣ RETURNING USER MESSAGE

**Trigger Condition:** User comes back the next day.

**Bot Logic:**
- On /start, check if last_used_date < today
- Reset usage_today = 0
- Send refreshed message

**Bot Message:**
```
👋 Welcome back, {first_name}!

Your daily free limit has been refreshed 🌙
Let's get your documents ready again.
```

**Inline Buttons:**
- 📂 Process Document  💎 Go Premium

---

## 📤 7️⃣ WHEN FILE IS RECEIVED

**Trigger Condition:** User sends or uploads a file.

**Bot Logic:**
- Detect file type (PDF, DOCX, JPG, PNG, etc)
- Save temporarily to data/ folder
- If free user → check if under daily limit
- Then show action options

**Bot Message:**
```
📄 File received successfully!
What would you like to do with it? 👇
```

**Inline Buttons:**
- 🔁 Convert File  📊 Merge PDFs
- ✂️ Split PDF  🗜️ Compress

---

## ⚙️ 8️⃣ PROCESSING STAGE

**Trigger Condition:** User chooses an operation.

**Bot Logic:**
- Depending on selected action:
  - Call tool in /tools folder (e.g. pdf_to_word.py, compress.py)
  - Show "Processing" message
- On completion → increment usage if free user

**Bot Message:**
```
⚙️ Please wait a moment...
Your document is being processed 🔄
```

---

## ✅ 9️⃣ SUCCESS STAGE

**Trigger Condition:** When file operation finishes successfully.

**Bot Logic:**
- Send the processed file using bot.send_document()
- Update usage counter

**Bot Message:**
```
✅ Done! Your document is ready 🎉
Click below to download your file 👇
```

**Inline Buttons:**
- ⬇️ Download File  💎 Upgrade for Unlimited Access

---

## ⚠️ 🔟 ERROR HANDLING

**Trigger Condition:** If file conversion fails, invalid format, or library error.

**Bot Logic:**
- Catch exception, log to /utils/error_handler.py
- Notify user politely

**Bot Message:**
```
⚠️ Oops! Something went wrong while processing your file.
Please try again later or contact @DocuLunaSupport
```

---

## 🎁 1️⃣1️⃣ REFERRAL SYSTEM

**Trigger Condition:** User taps "🎁 Refer & Earn".

**Bot Logic:**
- Generate unique referral link (https://t.me/DocuLunaBot?start=ref_{user_id})
- Store referrals in DB
- When referred user upgrades → credit ₦500 or ₦150 depending on plan

**Bot Message:**
```
🎁 Earn with DocuLuna!

Share your referral link and earn:
💰 ₦500 per Monthly Premium signup
💰 ₦150 per Weekly Premium signup

Invite your friends and get rewarded instantly 🌙
```

**Inline Buttons:**
- 🔗 Copy My Referral Link  ⬅️ Back

---

## 🔐 1️⃣2️⃣ ADMIN PANEL

**Trigger Condition:** Admin user (ID in ADMIN_USER_IDS) sends /admin.

**Bot Logic:**
- Verify user_id in admin list
- Show dashboard options for stats, payments, and broadcast

**Bot Message:**
```
👑 Admin Panel Access

Choose an action below:
📈 View Analytics
💰 View Payments
👥 Manage Users
📢 Broadcast Message
```

---

## 🌟 1️⃣3️⃣ OUTRO / GOODBYE MESSAGE

**Trigger Condition:** Optional closing or idle message.

**Bot Logic:**
- Shown when session ends or after inactivity

**Bot Message:**
```
🌙 DocuLuna Bot — made with ❤️ to make your document life easier.

🚀 Convert, Compress, and Manage — all in one place.
💎 Go Premium today to enjoy unlimited access!
```
