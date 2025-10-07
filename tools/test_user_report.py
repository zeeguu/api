#!/usr/bin/env python
"""
Quick test script for user article broken reporting system.
"""

from zeeguu.api.app import create_app
from zeeguu.core.model import Article, User, UserArticleBrokenReport, db
from zeeguu.core.model.article_broken_code_map import ArticleBrokenMap, LowQualityTypes

# Create Flask app context
app = create_app()

with app.app_context():
    print("=" * 80)
    print("USER ARTICLE BROKEN REPORT TEST")
    print("=" * 80)

    # Find a test article (just get any article)
    article = Article.query.filter(Article.broken == 0).first()
    if not article:
        print("ERROR: No non-broken articles found in database")
        exit(1)

    print(f"\nTest Article:")
    print(f"  ID: {article.id}")
    print(f"  Title: {article.title[:60]}...")

    # Find test users (2 regular + 1 teacher)
    regular_users = User.query.limit(2).all()

    # Try to find a teacher
    from zeeguu.core.model import Teacher
    teacher_obj = Teacher.query.first()
    teacher_user = teacher_obj.user if teacher_obj else None

    if len(regular_users) < 2:
        print(f"ERROR: Need at least 2 regular users, found only {len(regular_users)}")
        exit(1)

    print(f"\nTest Users:")
    for i, user in enumerate(regular_users, 1):
        print(f"  {i}. User ID: {user.id}, Name: {user.name} (regular)")

    if teacher_user:
        print(f"  3. User ID: {teacher_user.id}, Name: {teacher_user.name} (TEACHER)")
    else:
        print(f"  Note: No teacher found, will skip teacher test")

    # Clear any existing reports for this article
    existing_reports = UserArticleBrokenReport.all_for_article(db.session, article)
    for report in existing_reports:
        db.session.delete(report)
    db.session.commit()
    print(f"\n✓ Cleared {len(existing_reports)} existing reports")

    # Test: User 1 reports
    print("\n" + "-" * 80)
    print("TEST 1: First regular user reports (should NOT mark as broken)")
    print("-" * 80)
    report1, marked1 = UserArticleBrokenReport.create(
        db.session, regular_users[0], article, "Article has paywall"
    )
    count1 = UserArticleBrokenReport.count_for_article(db.session, article)
    print(f"✓ Report created by user {regular_users[0].id}")
    print(f"  Total reports: {count1}")
    print(f"  Marked as broken: {marked1}")
    assert count1 == 1, f"Expected 1 report, got {count1}"
    assert marked1 == False, "Should not mark as broken with 1 report"

    # Test: User 2 reports (threshold reached!)
    print("\n" + "-" * 80)
    print("TEST 2: Second regular user reports (SHOULD mark as broken - threshold=2)")
    print("-" * 80)
    report2, marked2 = UserArticleBrokenReport.create(
        db.session, regular_users[1], article, "Content is incomplete"
    )
    count2 = UserArticleBrokenReport.count_for_article(db.session, article)
    print(f"✓ Report created by user {regular_users[1].id}")
    print(f"  Total reports: {count2}")
    print(f"  Marked as broken: {marked2}")
    assert count2 == 2, f"Expected 2 reports, got {count2}"
    assert marked2 == True, "SHOULD mark as broken with 2 reports (threshold reached)!"

    # Verify article is marked with USER_REPORTED code
    broken_mark = ArticleBrokenMap.query.filter(
        ArticleBrokenMap.article_id == article.id,
        ArticleBrokenMap.broken_code == LowQualityTypes.USER_REPORTED
    ).first()

    print("\n" + "-" * 80)
    print("TEST 3: Verify article has USER_REPORTED code")
    print("-" * 80)
    assert broken_mark is not None, "Article should have USER_REPORTED broken code"
    print(f"✓ Article marked with code: {broken_mark.broken_code}")
    print(f"✓ Article broken status: {article.broken}")

    # Test: Same user tries to report again
    print("\n" + "-" * 80)
    print("TEST 4: Same user tries to report again (should return existing)")
    print("-" * 80)
    report_duplicate, marked_dup = UserArticleBrokenReport.create(
        db.session, regular_users[0], article, "Duplicate report"
    )
    count_dup = UserArticleBrokenReport.count_for_article(db.session, article)
    print(f"✓ Returned existing report for user {regular_users[0].id}")
    print(f"  Total reports: {count_dup}")
    assert count_dup == 2, f"Should still be 2 reports, got {count_dup}"
    assert report_duplicate.id == report1.id, "Should return same report object"

    # Test: Teacher reports (clean slate)
    if teacher_user:
        # Clean up previous test
        for report in UserArticleBrokenReport.all_for_article(db.session, article):
            db.session.delete(report)
        if broken_mark:
            db.session.delete(broken_mark)
        article.broken = 0
        db.session.commit()

        print("\n" + "-" * 80)
        print("TEST 5: Teacher reports (SHOULD mark immediately)")
        print("-" * 80)
        teacher_report, teacher_marked = UserArticleBrokenReport.create(
            db.session, teacher_user, article, "Teacher found issue"
        )
        teacher_count = UserArticleBrokenReport.count_for_article(db.session, article)
        print(f"✓ Report created by TEACHER user {teacher_user.id}")
        print(f"  Total reports: {teacher_count}")
        print(f"  Marked as broken: {teacher_marked}")
        assert teacher_count == 1, f"Expected 1 report, got {teacher_count}"
        assert teacher_marked == True, "Teacher report SHOULD mark immediately!"

        # Verify marked
        teacher_mark = ArticleBrokenMap.query.filter(
            ArticleBrokenMap.article_id == article.id,
            ArticleBrokenMap.broken_code == LowQualityTypes.USER_REPORTED
        ).first()
        assert teacher_mark is not None, "Article should be marked by teacher"
        print(f"✓ Article marked by teacher with code: {teacher_mark.broken_code}")

    # Get all reports with reasons
    print("\n" + "-" * 80)
    print(f"TEST {6 if teacher_user else 5}: Retrieve all reports")
    print("-" * 80)
    all_reports = UserArticleBrokenReport.all_for_article(db.session, article)
    for i, report in enumerate(all_reports, 1):
        print(f"  {i}. User {report.user_id}: '{report.reason}' at {report.report_time}")

    # Clean up
    print("\n" + "-" * 80)
    print("CLEANUP")
    print("-" * 80)
    # Refresh all_reports to get current state
    all_reports = UserArticleBrokenReport.all_for_article(db.session, article)
    for report in all_reports:
        db.session.delete(report)

    # Delete all broken marks for this article
    all_marks = ArticleBrokenMap.query.filter(
        ArticleBrokenMap.article_id == article.id
    ).all()
    for mark in all_marks:
        db.session.delete(mark)

    article.broken = 0
    db.session.commit()
    print("✓ Cleaned up test data")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED! ✓")
    print("=" * 80)
