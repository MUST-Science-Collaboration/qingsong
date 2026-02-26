# Qingsong User Manual & Demo Walkthrough

Welcome to **Qingsong** (青松)! This guide is designed for project managers and engineers who want a simple, reliable way to manage requirements, risks, and interfaces using a "Requirements as Code" philosophy.

---

## 1. Introduction: What is Qingsong?

Qingsong is a tool that helps you keep your project data (like requirements) in a structured, searchable, and traceable format. 

### Why use it?
- **Git Friendly**: Everything is stored in simple text files (YAML), making it easy to version control.
- **Searchable**: Includes a high-performance search engine.
- **Traceable**: Automatically maps relationships (e.g., "This requirement is satisfied by this document").
- **Portable**: One tool can manage many different projects ("Vaults").

---

## 2. Installation & Setup

Since you are likely already in the Qingsong development directory, you don't need to "install" anything globally. You have two excellent options for testing:

### Option A: Direct Testing (Recommended)
Use `uv run` to execute the command within the project's environment. This is the cleanest way to test without affecting your system.

```bash
# Verify the tool is working
uv run qingsong --version
```
*Note: In all examples below, replace `qingsong` with `uv run qingsong`.*

### Option B: The "Real User" Experience
If you want to use the `qingsong` command from anywhere (like a real user), you can install it into an isolated tool environment:

```bash
# Install qingsong as a standalone tool
uv tool install .

# Now you can use it anywhere!
qingsong --version
```

---

## 3. Demo Project: "The Mustard Coffee Shop"

We will learn Qingsong by building a small project from scratch: a smart coffee shop management system.

### Step 1: Initialize your project
Create a new folder for your project and initialize it as a Qingsong Vault.

```bash
mkdir coffee-shop
qingsong init ./coffee-shop --name "Mustard Coffee"
```

This creates the necessary folders:
- `meta/`: Where your "rules" live (who is on the team, what systems exist).
- `doorstop/`: Where your items (requirements, risks) live.

### Step 2: explore your team and systems
By default, `qingsong init` creates a basic team and system. Let's see them:

```bash
qingsong --root ./coffee-shop meta show
```

You'll see a system called `SYS/SUB` and people like `pm001` and `eng001`.

### Step 3: Create your first requirements
Let's define what our coffee shop needs. 

**Requirement 1: Order Processing**
```bash
qingsong --root ./coffee-shop new req \
  --title "Online Ordering" \
  --text "The system shall allow customers to place orders via a mobile app." \
  --system SYS/SUB \
  --owner pm001 \
  --category functional
```

**Requirement 2: Inventory Alert**
```bash
qingsong --root ./coffee-shop new req \
  --title "Low Bean Alert" \
  --text "The system shall notify the manager when coffee bean levels drop below 1kg." \
  --system SYS/SUB \
  --owner eng001 \
  --category functional
```

### Step 4: List and Search
Now that we have items, let's look at them.

**First, build the search index:**
Qingsong uses a high-performance index for searching. You should run this command after adding or changing items.

```bash
qingsong --root ./coffee-shop cache build
```

**Now you can list and search:**
```bash
# List all items
qingsong --root ./coffee-shop list

# Search for "coffee"
qingsong --root ./coffee-shop find "coffee"

# Show details of a specific item (use the ID from the list command)
qingsong --root ./coffee-shop show MUST-SYS-SUB-REQ-002
```

### Step 5: Managing Risks
Every project has risks. Let's add one.

```bash
qingsong --root ./coffee-shop new rsk \
  --title "Internet Outage" \
  --text "If the shop loses internet, online orders cannot be received." \
  --system SYS/SUB \
  --owner pm001
```

### Step 6: Validating your data
Qingsong ensures you don't make mistakes (like assigning an item to a person who isn't on the team).

```bash
qingsong --root ./coffee-shop validate
```

### Step 7: Generating Reports (Export)
You can turn your data into human-readable Markdown or CSV files for sharing.

```bash
# Export a requirements document
qingsong --root ./coffee-shop export requirements -o requirements.md

# Export everything to a CSV for Excel
qingsong --root ./coffee-shop export all --format csv -o data.csv
```

---

## 4. Advanced Concepts

### Manual YAML Editing
Since Qingsong is a "Requirements as Code" tool, you are free to edit the YAML files in the `doorstop/` folder directly using your favorite text editor (VS Code, Vim, etc.). 

**Crucial Note**: If you edit files manually, you bypass the tool's immediate safety checks. Always run the validation command after manual edits to ensure you haven't introduced any broken links or invalid metadata:

```bash
uv run qingsong --root ./coffee-shop validate
```

### Traceability
Qingsong can show you how items are linked.
 For example, if you link a "Test Record" to a "Requirement", Qingsong can generate a **Traceability Matrix** to show which requirements are verified.

```bash
qingsong --root ./coffee-shop trace --direction upward
```

### Migration
If you rename a system or move an item to a different folder, use the `migrate` command. It will automatically update the item's ID and fix all the links pointing to it!

```bash
# Move requirement 001 to a new system (if you defined one in meta/hierarchy.yaml)
qingsong --root ./coffee-shop migrate MUST-SYS-SUB-REQ-001 --system NEW/SYS
```

---

## 5. Summary of Key Commands

| Command | Usage |
| --- | --- |
| `qingsong init <path>` | Create a new project vault. |
| `qingsong --root <path> list` | View all items in a project. |
| `qingsong --root <path> new <type>` | Add a new requirement, risk, etc. |
| `qingsong --root <path> find "<query>"` | Search content using keywords. |
| `qingsong --root <path> export <type>` | Generate reports (Markdown/CSV). |
| `qingsong --root <path> validate` | Check for errors or inconsistencies. |

---

**Happy Project Managing!** If you have questions, refer to the `SPEC.md` or contact the MUST Project Team.
