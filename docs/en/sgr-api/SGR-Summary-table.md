## 📊 Summary Table of Agents

| Agent                                       | SGR Implementation | ReasoningTool        | Tools                 | API Requests | Selection Mechanism  |
| ------------------------------------------- | ------------------ | -------------------- | --------------------- | ------------ | -------------------- |
| **1. SGRAgent**                             | Structured Output  | ❌ Built into schema | 6 basic               | 1            | SO Union Type        |
| **2. ToolCallingAgent**                     | ❌ Absent          | ❌ Absent            | 6 basic               | 1            | FC "required"        |
| **3. SGRToolCallingAgent**                  | FC Tool enforced   | ✅ First step FC     | 7 (6 + ReasoningTool) | 2            | FC → FC    TOP AGENT |
| **4. SGRAutoToolCallingAgent** (deprecated) | FC Tool optional   | ✅ At model's choice | 7 (6 + ReasoningTool) | 1–2          | FC "auto"            |
| **5. SGRSOToolCallingAgent** (deprecated)   | FC → SO → FC auto  | ✅ FC enforced       | 7 (6 + ReasoningTool) | 3            | FC → SO → FC auto    |
