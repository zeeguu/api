#!/usr/bin/env python
"""
Genereaza o pagina simpla cu stirile zilei in limba romana.
Foloseste doar articolele simplificate la nivelul A2.
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../api"))

from zeeguu.api.app import create_app
from zeeguu.core.model import db, Article, Language
from sqlalchemy import and_, desc

app = create_app()
app.app_context().push()


def is_negative_news(article):
    """
    Determina daca un articol contine stiri negative folosind combinatie de filtre.
    """
    # First check with keywords for obvious negative content
    keyword_negative = _is_negative_news_keywords(article)
    
    # If keywords say it's negative, trust them (high precision)
    if keyword_negative:
        return True
    
    # If keywords say it's not negative, double-check with Anthropic API
    return _is_negative_news_anthropic(article)


def _is_negative_news_anthropic(article):
    """
    Foloseste Anthropic API pentru detectarea stirilor negative.
    """
    import anthropic
    import os
    
    try:
        # Get API key from environment
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("No Anthropic API key found, skipping AI analysis")
            return False
        
        # Prepare text for analysis (title + summary)
        text_parts = []
        if article.title:
            text_parts.append(f"Titlu: {article.title}")
        if article.summary:
            text_parts.append(f"Rezumat: {article.summary}")
        
        if not text_parts:
            return False
            
        text_to_analyze = '\n'.join(text_parts)
        
        # Create Anthropic client and analyze
        client = anthropic.Anthropic(api_key=api_key)
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": f"""Analizează următorul articol în română și determină dacă este o știre negativă.

Consideră ca negative: crime, violență, accidente, dezastre naturale, decese, boli grave, corupție, scandaluri, război, conflict, abuzuri, tragedii, probleme economice grave.

Nu considera ca negative: știri despre politică normală, sport, cultură, educație, tehnologie, vremea normală, evenimente pozitive.

Articol:
{text_to_analyze}

Răspunde doar cu "DA" dacă este negativă sau "NU" dacă nu este negativă."""
            }]
        )
        
        result = response.content[0].text.strip().upper()
        is_negative = result == "DA"
        
        # Debug output
        if is_negative:
            print(f"AI detected negative: {article.title[:50]}...")
            
        return is_negative
        
    except Exception as e:
        print(f"Error using Anthropic API for negative detection: {e}")
        return False


def _is_negative_news_keywords(article):
    """
    Fallback: Determina daca un articol contine stiri negative pe baza de cuvinte cheie.
    """
    negative_keywords = [
        # Crime and violence
        'mort', 'moarte', 'moare', 'ucis', 'omorât', 'crimă', 'criminal', 'asasinat',
        'împușcat', 'înjunghiat', 'bătut', 'violență', 'viol', 'agresiune', 'atac',
        
        # Accidents and disasters  
        'accident', 'accidentat', 'rănit', 'răniți', 'victimă', 'victime', 'explozie',
        'incendiu', 'cutremur', 'inundații', 'dezastru', 'catastrofă', 'prăbușit',
        
        # Disease and suffering
        'cancer', 'boală', 'bolnav', 'epidemie', 'pandemie', 'virus', 'infectat',
        'suferă', 'suferință', 'durere', 'spital', 'internat',
        
        # Corruption and scandals
        'corupție', 'corupt', 'șpagă', 'mită', 'scandal', 'fraudă', 'furt', 'furat',
        'arestat', 'reținut', 'condamnat', 'închisoare', 'pușcărie',
        
        # Economic problems
        'criză', 'faliment', 'șomaj', 'șomer', 'concediat', 'disponibilizat', 'sărăcie',
        'datorii', 'executat silit',
        
        # War and conflict
        'război', 'conflict', 'bombardament', 'bombardat', 'atacat', 'invazie',
        'refugiați', 'muniție', 'armă', 'militar',
        
        # Abuse and harassment
        'abuz', 'hărțuire', 'amenințare', 'amenințat', 'șantaj', 'intimidare',
        
        # Other negative terms
        'tragic', 'tragedie', 'groaznic', 'oribil', 'șocant', 'îngrozitor',
        'demis', 'destituit', 'investigat', 'cercetat penal'
    ]
    
    # Combine title and summary for analysis
    text_to_analyze = []
    if article.title:
        text_to_analyze.append(article.title.lower())
    if article.summary:
        text_to_analyze.append(article.summary.lower())
    
    full_text = ' '.join(text_to_analyze)
    
    # Check for negative keywords
    for keyword in negative_keywords:
        if keyword in full_text:
            return True
    
    return False


def is_too_complex_or_long(article):
    """
    Determina daca un articol este prea complex sau prea lung pentru nivelul A2.
    """
    # Complex vocabulary that might be difficult for A2 learners
    complex_keywords = [
        # Political/Economic jargon
        'restructurare', 'reorganizare', 'implementare', 'reglementare', 'legislație',
        'amendament', 'constituțional', 'parlamentar', 'guvernamental', 'administrativ',
        'bugetar', 'fiscal', 'monetary', 'investiții', 'finanțare', 'creditare',
        'inflație', 'devaluare', 'recesiune', 'dezvoltare economică',
        
        # Legal/Administrative terms
        'procedură', 'juridic', 'proces-verbal', 'hotărâre judecătorească', 
        'instanță', 'tribunal', 'curtea de apel', 'casație', 'normativ',
        'ordonanță', 'metodologie', 'reglementări', 'legislativ',
        'influențare', 'numiri', 'transparență', 'negocieri secrete',
        
        # Medical/Scientific terms
        'diagnostic', 'tratament', 'terapie', 'medicație', 'patologie',
        'chirurgie', 'intervenție', 'analize', 'investigații', 'tehnologii',
        'cercetare', 'studiu clinic', 'metodă', 'procedeu', 'sistem',
        
        # Complex concepts
        'strategie', 'implementare', 'dezvoltare', 'modernizare', 'digitalizare',
        'transformare', 'optimizare', 'eficientizare', 'reorganizare',
        'restructurare', 'consolidare', 'diversificare',
        
        # Foreign terms commonly used
        'management', 'marketing', 'leadership', 'business', 'startup',
        'corporate', 'networking', 'outsourcing', 'freelancer'
    ]
    
    # Combine title, summary and first part of content
    text_to_analyze = []
    if article.title:
        text_to_analyze.append(article.title.lower())
    if article.summary:
        text_to_analyze.append(article.summary.lower())
    if article.content:
        text_to_analyze.append(article.content[:300].lower())
    
    full_text = ' '.join(text_to_analyze)
    
    # Check length - title should be reasonable for A2
    if article.title and len(article.title) > 70:
        return True
        
    # Check summary length - should be concise
    if article.summary and len(article.summary) > 180:
        return True
    
    # Check content length - not too long for A2 readers
    if article.content and len(article.content) > 1500:
        return True
    
    # Count complex words in the text
    complex_word_count = 0
    for keyword in complex_keywords:
        if keyword in full_text:
            complex_word_count += 1
    
    # If too many complex words, filter out
    if complex_word_count > 2:
        return True
    
    # Check for very long sentences (might be too complex)
    if article.content:
        sentences = article.content.split('.')
        for sentence in sentences[:3]:  # Check first 3 sentences
            if len(sentence.strip()) > 150:  # Very long sentence
                return True
    
    return False


def get_recent_romanian_articles_a2(days_back=3, filter_negative=True, filter_complex=True):
    """
    Obtine articolele recente in romana simplificate la nivelul A2.
    Filtreaza stirile negative daca filter_negative=True.
    """
    cutoff_date = datetime.now() - timedelta(days=days_back)
    
    romanian = Language.find_or_create("ro")
    
    # Get more articles initially since we'll filter some out
    limit = 60 if (filter_negative or filter_complex) else 20
    
    articles = (
        Article.query
        .filter(
            and_(
                Article.cefr_level == "A2",
                Article.language_id == romanian.id,
                Article.published_time >= cutoff_date,
                Article.broken == 0,
                Article.deleted == 0,
                Article.parent_article_id != None  # Doar articole simplificate
            )
        )
        .order_by(desc(Article.published_time))
        .limit(limit)
        .all()
    )
    
    if filter_negative or filter_complex:
        # Filter out negative news and/or complex articles
        filtered_articles = []
        for article in articles:
            if filter_negative and is_negative_news(article):
                continue
            if filter_complex and is_too_complex_or_long(article):
                continue
            filtered_articles.append(article)
            # Stop when we have enough filtered articles
            if len(filtered_articles) >= 20:
                break
        
        filtered_count = len(articles) - len(filtered_articles)
        print(f"Filtered out {filtered_count} articles (negative: {filter_negative}, complex: {filter_complex})")
        print(f"Showing {len(filtered_articles)} suitable articles")
        return filtered_articles
    
    return articles


def generate_article_html(article):
    """
    Genereaza HTML pentru un singur articol (pagina completa).
    """
    html = f"""<!DOCTYPE html>
<html lang="ro">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>{article.title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 18px;
            line-height: 1.8;
            padding: 20px;
            max-width: 100%;
            background-color: #f5f5f5;
            color: #333;
        }}
        
        .back-button {{
            display: block;
            width: 100%;
            padding: 20px;
            background-color: #007AFF;
            color: white;
            text-align: center;
            text-decoration: none;
            font-size: 20px;
            font-weight: bold;
            border-radius: 10px;
            margin-bottom: 20px;
            border: none;
            cursor: pointer;
        }}
        
        .back-button:hover {{
            background-color: #0051D5;
        }}
        
        .article-container {{
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        h1 {{
            font-size: 28px;
            line-height: 1.3;
            margin-bottom: 15px;
            color: #1a1a1a;
        }}
        
        .meta {{
            font-size: 14px;
            color: #666;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid #e0e0e0;
        }}
        
        .content {{
            font-size: 18px;
            line-height: 1.8;
            color: #333;
        }}
        
        .content p {{
            margin-bottom: 15px;
        }}
        
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 20px 0;
            border-radius: 10px;
        }}
        
        @media (min-width: 768px) {{
            body {{
                max-width: 700px;
                margin: 0 auto;
            }}
        }}
    </style>
</head>
<body>
    <button onclick="history.back()" class="back-button">← Înapoi la știri</button>
    
    <div class="article-container">
        <h1>{article.title}</h1>
        <div class="meta">
            {article.published_time.strftime("%d %B %Y, %H:%M") if article.published_time else ""}
        </div>
        <div class="content">
            {article.htmlContent or article.content.replace(chr(10), '<br>' + chr(10)) if article.content else ''}
        </div>
    </div>
    
    <script>
        // Preserve portal URL from referrer if available
        if (document.referrer) {{
            const referrerUrl = new URL(document.referrer);
            const portalUrl = referrerUrl.searchParams.get('portal');
            if (portalUrl) {{
                sessionStorage.setItem('stirisimple_portal_url', portalUrl);
            }}
        }}
    </script>
</body>
</html>"""
    
    return html


def generate_index_html(articles, current_date):
    """
    Genereaza pagina principala cu lista de stiri, grupate pe date.
    """
    from datetime import datetime
    from collections import defaultdict
    
    # Format current date for display
    current_datetime = datetime.now()
    generated_time = current_datetime.strftime("%d %B %Y, %H:%M")
    
    # Romanian month names
    romanian_months = {
        'January': 'ianuarie', 'February': 'februarie', 'March': 'martie',
        'April': 'aprilie', 'May': 'mai', 'June': 'iunie',
        'July': 'iulie', 'August': 'august', 'September': 'septembrie',
        'October': 'octombrie', 'November': 'noiembrie', 'December': 'decembrie'
    }
    
    for eng, rom in romanian_months.items():
        generated_time = generated_time.replace(eng, rom)
    
    # Group articles by publication date
    articles_by_date = defaultdict(list)
    
    for article in articles:
        if article.published_time:
            pub_date = article.published_time.strftime("%Y-%m-%d")
            articles_by_date[pub_date].append(article)
        else:
            # Articles without publish date go to today
            articles_by_date[current_date].append(article)
    
    # Sort dates in descending order (newest first)
    sorted_dates = sorted(articles_by_date.keys(), reverse=True)
    
    articles_html = ""
    
    for date_key in sorted_dates:
        articles_for_date = articles_by_date[date_key]
        
        # Format date for display
        date_obj = datetime.strptime(date_key, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d %B %Y")
        for eng, rom in romanian_months.items():
            formatted_date = formatted_date.replace(eng, rom)
        
        # Add date header
        articles_html += f"""
        <h2 class="date-header">{formatted_date}</h2>
        """
        
        # Add articles for this date
        for article in articles_for_date:
            # Extrage prima imagine din continut (daca exista)
            image_html = ""
            if article.htmlContent and '<img' in article.htmlContent:
                import re
                img_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*>', article.htmlContent)
                if img_match:
                    image_html = f'<img src="{img_match.group(1)}" alt="" loading="lazy">'
            
            # Genereaza sumarul
            summary = article.summary or ""
            if not summary and article.content:
                summary = article.content[:200] + "..." if len(article.content) > 200 else article.content
            
            articles_html += f"""
            <article class="news-item">
                <a href="articles/{current_date}/article_{article.id}.html" class="news-link">
                    {image_html}
                    <h2>{article.title}</h2>
                    <p class="summary">{summary}</p>
                    <span class="read-more">Citește mai mult →</span>
                </a>
            </article>
            """
    
    html = f"""<!DOCTYPE html>
<html lang="ro">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>Știri - Română A2</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 16px;
            line-height: 1.6;
            padding: 20px;
            max-width: 100%;
            background-color: #f5f5f5;
            color: #333;
        }}
        
        .back-button {{
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            display: block;
            width: 90%;
            max-width: 300px;
            padding: 20px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            text-align: center;
            text-decoration: none;
            font-size: 22px;
            font-weight: bold;
            border-radius: 15px;
            border: none;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(240, 147, 251, 0.3);
        }}
        
        .back-button:hover {{
            transform: translateX(-50%) translateY(-2px);
            box-shadow: 0 6px 20px rgba(240, 147, 251, 0.4);
            background: linear-gradient(135deg, #e1467c 0%, #f04867 100%);
        }}
        
        .back-button:focus {{
            outline: 3px solid #FFD700;
            outline-offset: 2px;
        }}
        
        .generated-note {{
            font-size: 12px;
            text-align: center;
            color: #666;
            margin-bottom: 20px;
            font-style: italic;
        }}
        
        h1 {{
            font-size: 32px;
            text-align: center;
            margin-top: 100px;
            margin-bottom: 30px;
            color: #1a1a1a;
        }}
        
        .date-header {{
            font-size: 24px;
            color: #333;
            margin: 40px 0 20px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #007AFF;
            font-weight: 600;
        }}
        
        .date-header:first-child {{
            margin-top: 0px;
        }}
        
        .news-item {{
            background-color: white;
            margin-bottom: 20px;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .news-link {{
            display: block;
            padding: 20px;
            text-decoration: none;
            color: inherit;
        }}
        
        .news-link:hover {{
            background-color: #f9f9f9;
        }}
        
        .news-item img {{
            width: 100%;
            height: 200px;
            object-fit: cover;
            margin: -20px -20px 15px -20px;
            border-radius: 0;
        }}
        
        .news-item h2 {{
            font-size: 22px;
            line-height: 1.3;
            margin-bottom: 10px;
            color: #1a1a1a;
        }}
        
        .summary {{
            font-size: 16px;
            line-height: 1.6;
            color: #666;
            margin-bottom: 10px;
        }}
        
        .read-more {{
            font-size: 14px;
            color: #007AFF;
            font-weight: 600;
        }}
        
        .no-news {{
            text-align: center;
            padding: 40px;
            font-size: 18px;
            color: #666;
        }}
        
        @media (min-width: 768px) {{
            body {{
                max-width: 700px;
                margin: 0 auto;
            }}
            
            .news-item img {{
                height: 250px;
            }}
        }}
        
        /* Accessibility improvements */
        @media (prefers-reduced-motion: reduce) {{
            * {{
                animation: none !important;
                transition: none !important;
            }}
        }}
        
        @media (prefers-contrast: high) {{
            .news-item {{
                border: 2px solid #333;
            }}
            
            .read-more {{
                text-decoration: underline;
            }}
        }}
    </style>
</head>
<body>
    <a href="../index.html" class="back-button" id="backButton" style="display: block;" aria-label="Acasă">
        ← Acasă
    </a>
    
    <div class="generated-note">Generat la {generated_time}</div>
    <h1>Știri</h1>
    
    {articles_html if articles_html else '<div class="no-news">Nu sunt știri disponibile momentan.</div>'}

    <script>
        // Show back button if coming from portal (with persistent storage)
        const urlParams = new URLSearchParams(window.location.search);
        let portalUrl = urlParams.get('portal');
        
        // If portal URL is in current URL, store it in sessionStorage
        if (portalUrl) {{
            sessionStorage.setItem('stirisimple_portal_url', portalUrl);
        }} else {{
            // If not in URL, try to get it from sessionStorage
            portalUrl = sessionStorage.getItem('stirisimple_portal_url');
        }}
        
        // Show button if we have a portal URL from either source
        if (portalUrl) {{
            const backButton = document.getElementById('backButton');
            backButton.style.display = 'block';
            backButton.href = portalUrl;
        }}
    </script>
</body>
</html>"""
    
    return html


def main():
    """
    Genereaza paginile HTML.
    """
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Data curentă pentru structura de linkuri
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    print("Obținere articole din baza de date...")
    articles = get_recent_romanian_articles_a2(filter_negative=True, filter_complex=False)
    
    if not articles:
        print("Nu s-au găsit articole simplificate A2 în română.")
        # Genereaza pagina goala
        index_html = generate_index_html([], current_date)
        with open(output_dir / "index.html", "w", encoding="utf-8") as f:
            f.write(index_html)
        print(f"Pagină goală generată în: {output_dir / 'index.html'}")
        return
    
    print(f"S-au găsit {len(articles)} articole.")
    
    # Genereaza pagina principala
    index_html = generate_index_html(articles, current_date)
    with open(output_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"Pagină principală generată: {output_dir / 'index.html'}")
    
    # Genereaza paginile individuale pentru fiecare articol
    # Creează subdirectorul articles/data
    current_date = datetime.now().strftime("%Y-%m-%d")
    articles_date_dir = output_dir / "articles" / current_date
    articles_date_dir.mkdir(parents=True, exist_ok=True)
    
    for article in articles:
        article_html = generate_article_html(article)
        filename = f"article_{article.id}.html"
        with open(articles_date_dir / filename, "w", encoding="utf-8") as f:
            f.write(article_html)
        print(f"  - Articol generat: articles/{current_date}/{filename}")
    
    print(f"\nToate paginile au fost generate în: {output_dir}")
    print(f"Deschide {output_dir / 'index.html'} în browser pentru a vizualiza știrile.")


if __name__ == "__main__":
    main()