#!/usr/bin/env python
"""
Script care generează știrile și le deployează direct în zeeguu-news project.
"""

import sys
import os
import shutil
from pathlib import Path
from datetime import datetime

# Adaugă calea către zeeguu-api
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

def main():
    """Generează știrile și le copiază în proiectul zeeguu-news."""
    print("🚀 Generez știri pentru deployment...")

    # Rulează generatorul principal
    script_dir = Path(__file__).parent
    generate_script = script_dir / "generate_news_page.py"
    exit_code = os.system(f"python {generate_script}")
    
    if exit_code != 0:
        print("❌ Eroare la generarea știrilor")
        return False
        
    # Găsește calea către stiri-simple.github.io (mounted as volume in Docker)
    news_project_path = Path("/deployments/stiri-simple.github.io")
    output_path = Path(__file__).parent / "output"
    
    if not news_project_path.exists():
        print(f"❌ Proiectul stiri-simple nu a fost găsit la {news_project_path}")
        return False
        
    if not output_path.exists():
        print("❌ Nu s-au generat știri")
        return False
        
    print(f"📁 Copiez conținutul în {news_project_path}")
    
    # Copiază index.html
    shutil.copy(output_path / "index.html", news_project_path / "index.html")
    
    # Creează directorul articles dacă nu există
    articles_dir = news_project_path / "articles"
    articles_dir.mkdir(exist_ok=True)
    
    # Creează subdirectorul cu data curentă
    current_date = datetime.now().strftime("%Y-%m-%d")
    date_dir = articles_dir / current_date
    date_dir.mkdir(exist_ok=True)

    # Copiază articolele din subdirectorul articles/current_date
    source_articles_dir = output_path / "articles" / current_date

    if not source_articles_dir.exists():
        print(f"⚠️  Nu există director cu articole pentru {current_date}")
    else:
        for article_file in source_articles_dir.glob("article_*.html"):
            shutil.copy(article_file, date_dir / article_file.name)

    article_count = len(list(date_dir.glob("article_*.html")))
    
    print(f"✅ {article_count} articole copiate în stiri-simple.github.io")
    print(f"📄 index.html actualizat")
    
    # Git operations pentru deployment
    print("📦 Commitez și fac push...")

    # Schimbă în directorul proiectului de știri
    original_dir = os.getcwd()
    os.chdir(news_project_path)

    try:
        # Mark directory as safe for git operations
        os.system(f"git config --global --add safe.directory {news_project_path}")

        # Add toate fișierele
        exit_code = os.system("git add .")
        if exit_code != 0:
            print("❌ Eroare la git add")
            return False
            
        # Commit cu timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        commit_message = f"Update știri - {timestamp}"
        exit_code = os.system(f'git commit -m "{commit_message}"')
        if exit_code != 0:
            print("⚠️  Nu au fost găsite modificări de committat")
            return True  # Nu e o eroare dacă nu sunt modificări
            
        # Push
        exit_code = os.system("git push")
        if exit_code != 0:
            print("❌ Eroare la git push")
            return False
            
        print("🚀 Deployment complet! Site-ul va fi actualizat în ~5 minute.")
        
    finally:
        # Revin la directorul original
        os.chdir(original_dir)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)