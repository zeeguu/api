#!/usr/bin/env python
"""
Script to fix HTML content for existing simplified articles.
This corrects the issue where simplified articles were using the parent article's HTML content
instead of generating HTML from their simplified plain text content.
"""

import markdown2
from zeeguu.core.model import Article, db
from zeeguu.logging import log
from sqlalchemy import and_

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()


def fix_simplified_article_html(article):
    """
    Fix the HTML content for a simplified article by converting its plain text to HTML.
    """
    try:
        # Get the plain text content from the source
        plain_content = article.get_content()

        if not plain_content:
            log(f"WARNING: Article {article.id} has no content")
            return False

        # Convert plain text to markdown-formatted HTML
        # First check if it looks like markdown (has markdown formatting)
        has_markdown = any(
            marker in plain_content for marker in ["**", "##", "> ", "- ", "* ", "1. "]
        )

        if has_markdown:
            # Content appears to be markdown
            html_content = markdown2.markdown(
                plain_content,
                extras=["break-on-newline", "fenced-code-blocks", "tables"],
            )
        else:
            # Plain text - convert paragraphs to HTML
            paragraphs = plain_content.split("\n\n")
            html_content = "".join(
                [f"<p>{para.strip()}</p>" for para in paragraphs if para.strip()]
            )

        # Update the HTML content
        article.htmlContent = html_content

        log(f"Fixed HTML for article {article.id}: {article.title[:50]}...")
        return True

    except Exception as e:
        log(f"ERROR fixing article {article.id}: {e}")
        return False


def main():
    """
    Find and fix all simplified articles with incorrect HTML content.
    """
    log("Starting to fix simplified articles HTML content...")

    # Query for all simplified articles (those with parent_article_id)
    simplified_articles = Article.query.filter(
        Article.parent_article_id.isnot(None)
    ).all()

    log(f"Found {len(simplified_articles)} simplified articles to check")

    fixed_count = 0
    error_count = 0
    skipped_count = 0
    skipped_bookmarks_count = 0

    for article in simplified_articles:
        try:
            parent = Article.find_by_id(article.parent_article_id)
            if not parent:
                log(f"WARNING: Article {article.id} has no parent")
                error_count += 1
                continue

            # Check if the HTML content matches the parent's HTML (indicating the bug)
            html_matches = article.htmlContent == parent.htmlContent

            # Also check if plain text content is different (indicating it's truly simplified)
            simplified_content = article.get_content()
            parent_content = parent.get_content()
            content_is_different = simplified_content != parent_content
            
            # Check if article has any bookmarks - if so, skip to avoid breaking them
            from zeeguu.core.model.bookmark import Bookmark
            bookmark_count = Bookmark.query.filter_by(text_id=article.source.id).count()
            has_bookmarks = bookmark_count > 0

            if html_matches and content_is_different and not has_bookmarks:
                # HTML is wrong (copied from parent) but content is different (properly simplified)
                # AND no bookmarks exist - safe to fix
                log(f"\nFound article that needs fixing:")
                log(f"  Article ID: {article.id}")
                log(f"  Parent ID: {article.parent_article_id}")
                log(f"  Title: {article.title}")
                log(f"  CEFR Level: {article.cefr_level}")
                log(f"  HTML content matches parent: {html_matches}")
                log(f"  Plain text content is different: {content_is_different}")
                log(f"  Has bookmarks: {has_bookmarks}")

                log(f"Fixing article {article.id}...")
                if fix_simplified_article_html(article):
                    fixed_count += 1
                    db.session.add(article)
                    log(f"Successfully fixed article {article.id}")
                else:
                    error_count += 1
                    log(f"Failed to fix article {article.id}")
            elif html_matches and content_is_different and has_bookmarks:
                # Article needs fixing but has bookmarks - too risky
                log(f"\nSKIPPED: Article {article.id} needs fixing but has {bookmark_count} bookmarks - too risky")
                log(f"  Title: {article.title}")
                log(f"  CEFR Level: {article.cefr_level}")
                skipped_bookmarks_count += 1

            elif html_matches and not content_is_different:
                # Both HTML and content match parent - this is completely broken
                log(
                    f"ERROR: Article {article.id} has both HTML and content matching parent - needs re-simplification"
                )
                error_count += 1
            else:
                skipped_count += 1
                log(
                    f"Skipped article {article.id} - HTML already different from parent"
                )

            # Commit in batches of 10
            if fixed_count > 0 and fixed_count % 10 == 0:
                db.session.commit()
                log(f"Committed batch - fixed {fixed_count} articles so far")

        except Exception as e:
            log(f"ERROR processing article {article.id}: {e}")
            error_count += 1
            continue

    # Final commit
    if fixed_count > 0:
        db.session.commit()

    log(f"\n=== SUMMARY ===")
    log(f"Total simplified articles: {len(simplified_articles)}")
    log(f"Fixed: {fixed_count}")
    log(f"Skipped (different HTML): {skipped_count}")
    log(f"Skipped (has bookmarks): {skipped_bookmarks_count}")
    log(f"Errors: {error_count}")
    log(f"===============\n")

    if fixed_count > 0:
        log(f"SUCCESS: Fixed HTML content for {fixed_count} simplified articles!")
    else:
        log("No articles needed fixing.")


if __name__ == "__main__":
    main()
