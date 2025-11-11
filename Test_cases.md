That’s awesome — Blimp sounds like a very powerful automation platform 👏

Let’s build a **comprehensive and structured set of test cases** for it.
We'll organize them into **classes** based on each integrated app and **two main action types**:

- **Creation Actions** (create/update/post/schedule)
- **Inquiry Actions** (retrieve/search/ask about existing data)

Each test case will include:

- **ID**
- **Description**
- **Input Example (user query)**
- **Expected Behavior**

---

## 🧩 Test Case Structure Overview

| Category           | Apps Covered                                    |
| ------------------ | ----------------------------------------------- |
| A. Slack           | Send messages, query channels, users            |
| B. Trello          | Create cards, query boards/lists                |
| C. Google Calendar | Create meetings/events, query schedule          |
| D. Google Drive    | Upload files, query/search files                |
| E. Notion          | Create/update pages, query databases/pages      |
| F. GitHub          | Create issues/pull requests, query repos/issues |

---

# 🧪 A. Slack

### **A1. Slack – Creation Actions**

| ID   | Description                     | Example Input                                                               | Expected Behavior                        |
| ---- | ------------------------------- | --------------------------------------------------------------------------- | ---------------------------------------- |
| A1.1 | Send a message to a channel     | “Send a Slack message in #general saying ‘Welcome to the team!’”            | Message sent successfully to #general    |
| A1.2 | Send a DM                       | “Send Sonia a Slack message saying ‘Let’s meet at 2pm’”                     | DM sent to Sonia                         |
| A1.3 | Post a message with mention     | “Post in #engineering mentioning @raj ‘Build is ready for review.’”         | Message sent with proper mention         |
| A1.4 | Post message with attachments   | “Send a Slack message to #reports with today’s status.pdf attached”         | Message sent with file attached          |
| A1.5 | Schedule a Slack message        | “Schedule a Slack message for 9am tomorrow to #marketing: ‘Launch begins!’” | Message scheduled correctly              |
| A1.6 | Send message based on condition | “Send message to #alerts if Trello card ‘Server Down’ is created”           | Conditional workflow triggers Slack post |

### **A2. Slack – Inquiry Actions**

| ID   | Description              | Example Input                                | Expected Behavior               |
| ---- | ------------------------ | -------------------------------------------- | ------------------------------- |
| A2.1 | Query recent messages    | “Show me last 5 messages from #general”      | Displays messages               |
| A2.2 | List channels            | “List all Slack channels I’m part of”        | Returns list of channels        |
| A2.3 | List users               | “Who’s in the #devops channel?”              | Returns member list             |
| A2.4 | Search messages          | “Find Slack messages mentioning ‘Q4 report’” | Returns relevant messages       |
| A2.5 | Check scheduled messages | “Do I have any scheduled Slack messages?”    | Returns pending scheduled posts |

---

# 🧪 B. Trello

### **B1. Trello – Creation Actions**

| ID   | Description       | Example Input                                                  | Expected Behavior         |
| ---- | ----------------- | -------------------------------------------------------------- | ------------------------- |
| B1.1 | Create a new card | “Create a Trello card ‘Fix login bug’ in ‘Backend Tasks’ list” | Card created successfully |
| B1.2 | Assign members    | “Assign Sonia to Trello card ‘Update docs’”                    | Member assigned           |
| B1.3 | Add due date      | “Set due date for Trello card ‘API Upgrade’ to next Friday”    | Due date updated          |
| B1.4 | Add checklist     | “Add checklist ‘Testing Steps’ to Trello card ‘Release 1.1’”   | Checklist added           |
| B1.5 | Move card         | “Move Trello card ‘Finalize UI’ to ‘Done’ list”                | Card moved successfully   |

### **B2. Trello – Inquiry Actions**

| ID   | Description        | Example Input                                          | Expected Behavior                            |
| ---- | ------------------ | ------------------------------------------------------ | -------------------------------------------- |
| B2.1 | List all boards    | “Show me all my Trello boards”                         | Returns list of boards                       |
| B2.2 | Show cards in list | “What’s in the ‘In Progress’ list on ‘Web App’ board?” | Displays list of cards                       |
| B2.3 | Show due today     | “Which Trello cards are due today?”                    | Lists matching cards                         |
| B2.4 | Find card          | “Search Trello for card ‘Database Migration’”          | Returns matching card                        |
| B2.5 | Card details       | “Show details of Trello card ‘Q1 Roadmap’”             | Returns description, due date, members, etc. |

---

# 🧪 C. Google Calendar

### **C1. Calendar – Creation Actions**

| ID   | Description      | Example Input                                                           | Expected Behavior  |
| ---- | ---------------- | ----------------------------------------------------------------------- | ------------------ |
| C1.1 | Create meeting   | “Schedule a Google Calendar meeting with Sonia for tomorrow at 3pm”     | Event created      |
| C1.2 | Add location     | “Create a Google Calendar event ‘Team Lunch’ at ‘Pasta Bar’ 1pm Friday” | Location added     |
| C1.3 | Add guests       | “Add Raj and Anna to meeting ‘Design Review’”                           | Guests invited     |
| C1.4 | Recurring events | “Set up a recurring event every Monday 9am ‘Sprint Planning’”           | Recurrence created |
| C1.5 | Cancel meeting   | “Cancel tomorrow’s meeting with Sonia”                                  | Event deleted      |

### **C2. Calendar – Inquiry Actions**

| ID   | Description         | Example Input                             | Expected Behavior                 |
| ---- | ------------------- | ----------------------------------------- | --------------------------------- |
| C2.1 | View today’s events | “What’s on my calendar today?”            | Displays events                   |
| C2.2 | View next meeting   | “When’s my next meeting?”                 | Returns next upcoming event       |
| C2.3 | Search events       | “Find meetings with Sonia this week”      | Returns matching events           |
| C2.4 | Check availability  | “Am I free Friday 2–4pm?”                 | Returns availability status       |
| C2.5 | Event details       | “Show details of ‘Budget Review’ meeting” | Displays details, attendees, time |

---

# 🧪 D. Google Drive

### **D1. Drive – Creation Actions**

| ID   | Description   | Example Input                                             | Expected Behavior   |
| ---- | ------------- | --------------------------------------------------------- | ------------------- |
| D1.1 | Upload file   | “Upload ‘report.pdf’ to Google Drive folder ‘Reports’”    | File uploaded       |
| D1.2 | Create folder | “Create a folder called ‘Project X Docs’ in Google Drive” | Folder created      |
| D1.3 | Share file    | “Share ‘budget.xlsx’ with Sonia”                          | Permissions updated |
| D1.4 | Rename file   | “Rename ‘Q3 report.pdf’ to ‘Q3 Final Report.pdf’”         | File renamed        |
| D1.5 | Move file     | “Move ‘notes.txt’ to folder ‘Archives’”                   | File moved          |

### **D2. Drive – Inquiry Actions**

| ID   | Description          | Example Input                                | Expected Behavior        |
| ---- | -------------------- | -------------------------------------------- | ------------------------ |
| D2.1 | Search files         | “Find Google Drive files named ‘invoice’”    | Returns matching files   |
| D2.2 | List folder contents | “Show contents of ‘Project X Docs’”          | Displays files/folders   |
| D2.3 | Recently modified    | “Show me recently edited Google Drive files” | Returns recent list      |
| D2.4 | File details         | “Who has access to ‘project plan.docx’?”     | Returns permissions info |
| D2.5 | Storage usage        | “How much Google Drive space am I using?”    | Returns usage stats      |

---

# 🧪 E. Notion

### **E1. Notion – Creation Actions**

| ID   | Description        | Example Input                                                                       | Expected Behavior |
| ---- | ------------------ | ----------------------------------------------------------------------------------- | ----------------- |
| E1.1 | Create new page    | “Create a Notion page ‘Q4 Objectives’ under ‘Company Goals’”                        | Page created      |
| E1.2 | Add database entry | “Add a new task to Notion database ‘Product Roadmap’ with title ‘Add chat support’” | Entry created     |
| E1.3 | Update field       | “Set status of ‘Add chat support’ to ‘In Progress’ in Notion”                       | Field updated     |
| E1.4 | Add content block  | “Add a bullet point ‘Review by design team’ under ‘Q4 Objectives’”                  | Block added       |
| E1.5 | Duplicate page     | “Duplicate Notion page ‘Sprint Template’”                                           | Page duplicated   |

### **E2. Notion – Inquiry Actions**

| ID   | Description             | Example Input                                               | Expected Behavior        |
| ---- | ----------------------- | ----------------------------------------------------------- | ------------------------ |
| E2.1 | List pages              | “Show all pages under ‘Marketing’ workspace”                | Returns list             |
| E2.2 | Search page             | “Find Notion page ‘Team Charter’”                           | Returns page             |
| E2.3 | Retrieve database items | “Show all tasks marked ‘In Progress’ in ‘Roadmap’ database” | Returns matching entries |
| E2.4 | Show page content       | “Open ‘Q4 Objectives’ page”                                 | Displays blocks/content  |
| E2.5 | Last updated pages      | “Which Notion pages were updated recently?”                 | Returns recent list      |

---

# 🧪 F. GitHub

### **F1. GitHub – Creation Actions**

| ID   | Description         | Example Input                                                            | Expected Behavior     |
| ---- | ------------------- | ------------------------------------------------------------------------ | --------------------- |
| F1.1 | Create issue        | “Create a GitHub issue in repo ‘blimp-core’ titled ‘Fix API timeout’”    | Issue created         |
| F1.2 | Assign issue        | “Assign issue #24 to Sonia”                                              | Assignment successful |
| F1.3 | Create pull request | “Create a PR from branch ‘feature/login’ to ‘main’ in repo ‘blimp-core’” | PR created            |
| F1.4 | Comment on issue    | “Comment ‘Will be fixed in v1.2’ on issue #45”                           | Comment added         |
| F1.5 | Close issue         | “Close GitHub issue #18”                                                 | Issue closed          |

### **F2. GitHub – Inquiry Actions**

| ID   | Description   | Example Input                                      | Expected Behavior                         |
| ---- | ------------- | -------------------------------------------------- | ----------------------------------------- |
| F2.1 | List issues   | “Show all open GitHub issues in repo ‘blimp-core’” | Returns list                              |
| F2.2 | Show PRs      | “List pull requests assigned to me”                | Returns list                              |
| F2.3 | Search repo   | “Find repos containing ‘workflow’ in the name”     | Returns repos                             |
| F2.4 | Show commits  | “Show latest commits in ‘blimp-core’”              | Displays commits                          |
| F2.5 | Issue details | “Show details for issue #32 in ‘blimp-core’”       | Returns title, status, assignee, comments |

---

# ✅ Summary of Test Classes

| Class ID | App             | Focus                |
| -------- | --------------- | -------------------- |
| A1–A2    | Slack           | Messaging & queries  |
| B1–B2    | Trello          | Task management      |
| C1–C2    | Google Calendar | Scheduling           |
| D1–D2    | Google Drive    | File management      |
| E1–E2    | Notion          | Knowledge management |
| F1–F2    | GitHub          | Development workflow |

---
