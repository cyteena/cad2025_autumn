#!/usr/bin/env python3
"""
快速生成 hw3 和 hw4 的脚本，跳过教程和依赖安装
"""
import os
import re
import sys
import subprocess
from pathlib import Path
import requests
from openai import OpenAI

# 配置
BASE_URL = "http://staff.ustc.edu.cn/~renjiec/cagd2025/"
DATA_URL = BASE_URL + "courseData.json"
GITHUB_USER = "cyteena"

# 初始化 OpenAI 客户端
api_key = os.environ.get("GEMINI_API_KEY")
base_url = os.environ.get("GOOGLE_GEMINI_BASE_URL", "http://127.0.0.1:8000")
if not base_url.endswith("/v1"):
    base_url = base_url.rstrip("/") + "/v1"

client = OpenAI(api_key=api_key, base_url=base_url)

def download_file(file_url, destination_path):
    """下载文件"""
    try:
        print(f"  - Downloading: {file_url}")
        response = requests.get(file_url, stream=True, timeout=15)
        response.raise_for_status()
        with open(destination_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"  ✔ Saved to: {destination_path}")
        return True
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return False

def setup_project(project_path: Path):
    """设置项目"""
    print(f"  - Initializing project: {project_path.name}...")
    try:
        project_path.mkdir(exist_ok=True)
        subprocess.run(["uv", "init", "--quiet"], cwd=project_path, check=True)
        subprocess.run(["uv", "venv"], cwd=project_path, check=True)
        subprocess.run(["rm", "main.py"], cwd=project_path, check=True)
        subprocess.run(["git", "init"], cwd=project_path, check=True)
        subprocess.run(["git", "add", "."], cwd=project_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_path, check=True, capture_output=True)
        print(f"  ✔ Project initialized.")
        return True
    except Exception as e:
        print(f"  ❌ Project setup failed: {e}")
        return False

def convert_pdf_to_markdown(pdf_path: Path):
    """转换 PDF 为 Markdown"""
    md_path = pdf_path.with_suffix(".md")
    print(f"  - Converting {pdf_path.name} to Markdown...")
    try:
        command = f'pdftotext "{pdf_path}" - | pandoc -f commonmark -t markdown -o "{md_path}"'
        subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"  ✔ Converted to: {md_path}")
    except Exception as e:
        print(f"  ❌ PDF conversion failed: {e}")

def generate_code_solution(hw_path: Path):
    """生成代码解决方案"""
    print(f"  - Preparing to generate code for {hw_path.name}...")
    try:
        requirement_file = next(hw_path.glob("*.md"))
        requirement_content = requirement_file.read_text()
    except StopIteration:
        print("  ❌ Could not find .md file for LLM context.")
        return None

    # 尝试找到 .py 模板文件
    try:
        template_file = next(hw_path.glob("*.py"))
        template_content = template_file.read_text()
        has_template = True
    except StopIteration:
        template_content = None
        has_template = False

    # 构建提示词
    if has_template:
        full_prompt = f"""
You are an expert Python programmer. Your task is to write clean, efficient, and correct code based on the provided requirements and code template.

Here are the requirements for a programming assignment:
--- REQUIREMENT ---
{requirement_content}
--- END REQUIREMENT ---

Here is the Python code template to be completed:
--- CODE TEMPLATE ---
{template_content}
--- END CODE TEMPLATE ---

**If the task requires interactive plotting, add the following before importing `matplotlib.pyplot`:**

```python
import matplotlib
matplotlib.use("Qt5Agg")
```

Please complete the Python code template based *only* on the requirements provided.
Your output must be ONLY the final, complete Python code for the template file. Do not include any explanations, introductory sentences, or markdown code blocks like ```python. Just provide the raw code.
"""
    else:
        full_prompt = f"""
You are an expert Python programmer. Your task is to write clean, efficient, and correct code based on the provided requirements.

Here are the requirements for a programming assignment:
--- REQUIREMENT ---
{requirement_content}
--- END REQUIREMENT ---

**If the task requires interactive plotting, add the following before importing `matplotlib.pyplot`:**

```python
import matplotlib
matplotlib.use("Qt5Agg")
```

Please write a complete Python solution based *only* on the requirements provided.
Your output must be ONLY the final, complete Python code. Do not include any explanations, introductory sentences, or markdown code blocks like ```python. Just provide the raw code.
"""
    
    print("  - Sending request to API for code generation...")
    try:
        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        clean_code = response.choices[0].message.content.strip().replace("```python", "").replace("```", "").strip()
        print("  ✔ Code generation successful.")
        return clean_code
    except Exception as e:
        print(f"  ❌ An error occurred while calling the API:")
        print(f"  Error details: {str(e)}")
        return None

def create_and_push_hw_repo(hw_path: Path, repo_name: str, github_user: str):
    """创建并推送 GitHub 仓库"""
    full_repo_name = f"{github_user}/{repo_name}"
    print(f"  - Creating GitHub repository: {full_repo_name}...")

    try:
        command = [
            "gh", "repo", "create", full_repo_name,
            "--public",
            "--source=.",
            "--remote=origin"
        ]
        subprocess.run(command, cwd=hw_path, check=True, capture_output=True, text=True)
        print("  ✔ GitHub repository created.")

        # Push
        try:
            subprocess.run(["git", "push", "-u", "origin", "master", "-f"], cwd=hw_path, check=True, capture_output=True)
            print("  ✔ Pushed to origin master.")
        except subprocess.CalledProcessError:
            subprocess.run(["git", "push", "-u", "origin", "main", "-f"], cwd=hw_path, check=True, capture_output=True)
            print("  ✔ Pushed to origin main.")

        return True
    except subprocess.CalledProcessError as e:
        if "already exists" in str(e.stderr):
            print(f"  - Repository already exists on GitHub. Skipping creation.")
            return True
        else:
            print(f"  ❌ Failed to create GitHub repository: {e}")
            return False

def add_submodule(hw_path: Path, hw_number: str):
    """添加子模块"""
    print(f"  - Adding {hw_path.name} as a submodule...")
    try:
        hw_repo_name = f"cagd2025-hw{hw_number}"
        hw_repo_url = f"https://github.com/{GITHUB_USER}/{hw_repo_name}.git"
        subprocess.run(
            ["git", "submodule", "add", hw_repo_url, str(hw_path)],
            cwd=".",
            check=True,
            capture_output=True
        )
        print(f"  ✔ Submodule added successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Failed to add submodule: {e.stderr.decode()}")
        return False

def main():
    """主函数"""
    print("--- Quick Homework Generator ---")
    
    # 获取课程数据
    try:
        response = requests.get(DATA_URL)
        response.raise_for_status()
        course_data = response.json()
        homework_items = next(
            s for s in course_data["assignments"]["sections"] if s["title"] == "Homework"
        ).get("items", [])
    except Exception as e:
        print(f"❌ Could not fetch course data: {e}")
        return
    
    # 只处理 hw3 和 hw4
    for item in homework_items:
        hw_title = item.get("text")
        if not hw_title:
            continue
        
        match = re.search(r'\d+', hw_title)
        if not match:
            continue

        hw_number = match.group(0)
        
        # 只处理 hw3 和 hw4
        if hw_number not in ["3", "4"]:
            continue

        hw_path = Path(".") / f"hw{hw_number}"
        print(f"\n[*] Processing: {hw_title}")

        # 检查是否已存在
        if hw_path.exists():
            print(f"  - Project already exists. Skipping.")
            continue

        # 设置项目
        if not setup_project(hw_path):
            continue

        # 下载文件
        files_to_download = [f for f in [item.get("file")] + [ef.get("file") for ef in item.get("extra_files", []) if "Python" in ef.get("text", "")] if f]
        for filename in files_to_download:
            full_url = BASE_URL + filename
            destination = hw_path / filename
            if download_file(full_url, destination) and destination.suffix == ".pdf":
                convert_pdf_to_markdown(destination)

        # 生成代码
        suggested_code = generate_code_solution(hw_path)

        if suggested_code:
            solution_path = hw_path / "solution_suggestion.py"
            try:
                solution_path.write_text(suggested_code)
                print(f"  ✔ AI-generated solution saved.")
                subprocess.run(["git", "add", "."], cwd=hw_path, check=True, capture_output=True)
                subprocess.run(["git", "commit", "-m", f"Add solution for {hw_title}"], cwd=hw_path, check=True, capture_output=True)
            except Exception as e:
                print(f"  ❌ Failed to save solution: {e}")

        # 创建并推送 GitHub 仓库
        hw_repo_name = f"cagd2025-hw{hw_number}"
        if not create_and_push_hw_repo(hw_path, hw_repo_name, GITHUB_USER):
            continue
        
        # 添加子模块
        add_submodule(hw_path, hw_number)

    # 提交主仓库的更改
    print(f"\n[*] Committing changes to main repository...")
    try:
        subprocess.run(["git", "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add hw3 and hw4 submodules", "--allow-empty"], check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", "master"], check=True, capture_output=True)
        print("✔ Changes pushed to main repository.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to commit/push: {e}")

    print("\n--- Finished ---")

if __name__ == "__main__":
    main()
