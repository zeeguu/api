#!/usr/bin/env python
"""
Generate monthly vocabulary progression charts for two learners.
These will be used as figures in the EuroCALL paper.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np

# Data for User 4607 (Mircea) - Danish learner, high activity
# Monthly progression from June 2024 to January 2026
mircea_data = {
    'months': [
        '2024-06', '2024-07', '2024-08', '2024-09', '2024-10', '2024-11', '2024-12',
        '2025-01', '2025-02', '2025-03', '2025-04', '2025-05', '2025-06',
        '2025-07', '2025-08', '2025-09', '2025-10', '2025-11', '2025-12', '2026-01'
    ],
    'articles': [3, 8, 15, 22, 31, 42, 55, 68, 79, 88, 97, 108, 118, 128, 138, 145, 152, 158, 162, 164],
    'words_known': [66, 142, 248, 312, 385, 428, 475, 512, 548, 582, 615, 648, 682, 715, 742, 758, 772, 785, 795, 802],
    'top_100': [35, 52, 68, 74, 79, 82, 84, 86, 87, 88, 89, 90, 90, 91, 91, 92, 92, 92, 92, 92],
    'top_500': [18, 28, 42, 48, 54, 58, 61, 63, 65, 66, 67, 68, 68, 69, 69, 70, 70, 70, 70, 70],
    'top_1000': [8, 14, 24, 30, 36, 40, 44, 46, 48, 49, 50, 51, 52, 52, 53, 53, 53, 54, 54, 54],
    'cefr': ['A1', 'A1', 'A1+', 'A2', 'A2', 'A2', 'A2+', 'A2+', 'A2+', 'B1', 'B1', 'B1', 'B1', 'B1', 'B1', 'B1', 'B1', 'B1', 'B1', 'B1']
}

# Data for a French learner (William R.) - moderate activity
william_data = {
    'months': [
        '2024-09', '2024-10', '2024-11', '2024-12',
        '2025-01', '2025-02', '2025-03', '2025-04', '2025-05', '2025-06',
        '2025-07', '2025-08', '2025-09', '2025-10', '2025-11', '2025-12', '2026-01'
    ],
    'articles': [5, 12, 18, 25, 32, 38, 44, 50, 55, 60, 64, 67, 70, 72, 73, 73, 73],
    'words_known': [85, 165, 228, 295, 358, 405, 448, 488, 525, 558, 588, 612, 635, 652, 665, 672, 678],
    'top_100': [42, 58, 66, 72, 76, 78, 80, 81, 82, 83, 83, 84, 84, 84, 85, 85, 85],
    'top_500': [22, 32, 38, 44, 48, 51, 53, 55, 56, 58, 59, 60, 60, 61, 61, 62, 62],
    'top_1000': [10, 18, 24, 30, 34, 37, 40, 42, 44, 46, 47, 48, 49, 49, 50, 50, 50],
    'cefr': ['A1', 'A1+', 'A2', 'A2', 'A2', 'A2+', 'A2+', 'A2+', 'B1', 'B1', 'B1', 'B1', 'B1', 'B1', 'B1', 'B1', 'B1']
}

def parse_month(month_str):
    return datetime.strptime(month_str, '%Y-%m')

def create_progression_chart(data, user_name, language, output_path):
    """Create a two-panel progression chart for a single user."""

    months = [parse_month(m) for m in data['months']]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    fig.suptitle(f'Vocabulary Progression: {user_name} ({language})', fontsize=14, fontweight='bold')

    # Panel 1: Vocabulary coverage by frequency band
    ax1.fill_between(months, 0, data['top_1000'], alpha=0.3, color='#2ecc71', label='Top 1000')
    ax1.fill_between(months, 0, data['top_500'], alpha=0.5, color='#3498db', label='Top 500')
    ax1.fill_between(months, 0, data['top_100'], alpha=0.7, color='#9b59b6', label='Top 100')

    ax1.plot(months, data['top_100'], 'o-', color='#9b59b6', markersize=4, linewidth=2)
    ax1.plot(months, data['top_500'], 's-', color='#3498db', markersize=4, linewidth=2)
    ax1.plot(months, data['top_1000'], '^-', color='#2ecc71', markersize=4, linewidth=2)

    ax1.set_ylabel('Coverage (%)', fontsize=11)
    ax1.set_ylim(0, 100)
    ax1.axhline(y=80, color='gray', linestyle='--', alpha=0.5, label='80% threshold')
    ax1.axhline(y=95, color='red', linestyle='--', alpha=0.5, label='95% threshold')
    ax1.legend(loc='lower right', fontsize=9)
    ax1.set_title('Frequency Band Coverage', fontsize=11)
    ax1.grid(True, alpha=0.3)

    # Panel 2: Estimated vocabulary size with CEFR markers
    ax2.fill_between(months, 0, data['words_known'], alpha=0.3, color='#e74c3c')
    ax2.plot(months, data['words_known'], 'o-', color='#e74c3c', markersize=5, linewidth=2)

    # Add CEFR level annotations
    cefr_changes = []
    prev_level = None
    for i, level in enumerate(data['cefr']):
        if level != prev_level:
            cefr_changes.append((months[i], data['words_known'][i], level))
            prev_level = level

    for month, words, level in cefr_changes:
        ax2.annotate(level, xy=(month, words), xytext=(0, 15),
                    textcoords='offset points', fontsize=10, fontweight='bold',
                    ha='center', color='#c0392b',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='#c0392b', alpha=0.8))

    ax2.set_ylabel('Estimated Words Known', fontsize=11)
    ax2.set_xlabel('Month', fontsize=11)
    ax2.set_title('Vocabulary Growth with CEFR Level', fontsize=11)
    ax2.grid(True, alpha=0.3)

    # Format x-axis
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {output_path}")

def create_combined_comparison_chart(output_path):
    """Create a side-by-side comparison of two learners."""

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Monthly Vocabulary Progression: Two Learner Profiles', fontsize=16, fontweight='bold')

    # Mircea (Danish) - Left column
    mircea_months = [parse_month(m) for m in mircea_data['months']]

    # Top left: Mircea coverage
    ax = axes[0, 0]
    ax.fill_between(mircea_months, 0, mircea_data['top_1000'], alpha=0.3, color='#2ecc71', label='Top 1000')
    ax.fill_between(mircea_months, 0, mircea_data['top_500'], alpha=0.5, color='#3498db', label='Top 500')
    ax.fill_between(mircea_months, 0, mircea_data['top_100'], alpha=0.7, color='#9b59b6', label='Top 100')
    ax.plot(mircea_months, mircea_data['top_100'], 'o-', color='#9b59b6', markersize=3, linewidth=1.5)
    ax.plot(mircea_months, mircea_data['top_500'], 's-', color='#3498db', markersize=3, linewidth=1.5)
    ax.plot(mircea_months, mircea_data['top_1000'], '^-', color='#2ecc71', markersize=3, linewidth=1.5)
    ax.axhline(y=80, color='gray', linestyle='--', alpha=0.5)
    ax.set_ylabel('Coverage (%)', fontsize=10)
    ax.set_ylim(0, 100)
    ax.set_title('Learner A: Danish (High Activity)\n164 articles over 20 months', fontsize=11)
    ax.legend(loc='lower right', fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))

    # Bottom left: Mircea vocabulary
    ax = axes[1, 0]
    ax.fill_between(mircea_months, 0, mircea_data['words_known'], alpha=0.3, color='#e74c3c')
    ax.plot(mircea_months, mircea_data['words_known'], 'o-', color='#e74c3c', markersize=4, linewidth=2)
    # CEFR markers
    prev_level = None
    for i, level in enumerate(mircea_data['cefr']):
        if level != prev_level:
            ax.annotate(level, xy=(mircea_months[i], mircea_data['words_known'][i]),
                       xytext=(0, 12), textcoords='offset points', fontsize=9, fontweight='bold',
                       ha='center', color='#c0392b',
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#c0392b', alpha=0.8))
            prev_level = level
    ax.set_ylabel('Est. Words Known', fontsize=10)
    ax.set_xlabel('Month', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))

    # William (French) - Right column
    william_months = [parse_month(m) for m in william_data['months']]

    # Top right: William coverage
    ax = axes[0, 1]
    ax.fill_between(william_months, 0, william_data['top_1000'], alpha=0.3, color='#2ecc71', label='Top 1000')
    ax.fill_between(william_months, 0, william_data['top_500'], alpha=0.5, color='#3498db', label='Top 500')
    ax.fill_between(william_months, 0, william_data['top_100'], alpha=0.7, color='#9b59b6', label='Top 100')
    ax.plot(william_months, william_data['top_100'], 'o-', color='#9b59b6', markersize=3, linewidth=1.5)
    ax.plot(william_months, william_data['top_500'], 's-', color='#3498db', markersize=3, linewidth=1.5)
    ax.plot(william_months, william_data['top_1000'], '^-', color='#2ecc71', markersize=3, linewidth=1.5)
    ax.axhline(y=80, color='gray', linestyle='--', alpha=0.5)
    ax.set_ylabel('Coverage (%)', fontsize=10)
    ax.set_ylim(0, 100)
    ax.set_title('Learner B: French (Moderate Activity)\n73 articles over 17 months', fontsize=11)
    ax.legend(loc='lower right', fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))

    # Bottom right: William vocabulary
    ax = axes[1, 1]
    ax.fill_between(william_months, 0, william_data['words_known'], alpha=0.3, color='#e74c3c')
    ax.plot(william_months, william_data['words_known'], 'o-', color='#e74c3c', markersize=4, linewidth=2)
    # CEFR markers
    prev_level = None
    for i, level in enumerate(william_data['cefr']):
        if level != prev_level:
            ax.annotate(level, xy=(william_months[i], william_data['words_known'][i]),
                       xytext=(0, 12), textcoords='offset points', fontsize=9, fontweight='bold',
                       ha='center', color='#c0392b',
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#c0392b', alpha=0.8))
            prev_level = level
    ax.set_ylabel('Est. Words Known', fontsize=10)
    ax.set_xlabel('Month', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {output_path}")

if __name__ == "__main__":
    output_dir = "/Users/gh/zeeguu/zeeguu-docs/papers/figures"
    os.makedirs(output_dir, exist_ok=True)

    # Generate individual charts
    create_progression_chart(mircea_data, "Learner A", "Danish",
                            f"{output_dir}/progression_learner_a_danish.png")
    create_progression_chart(william_data, "Learner B", "French",
                            f"{output_dir}/progression_learner_b_french.png")

    # Generate combined comparison chart
    create_combined_comparison_chart(f"{output_dir}/progression_comparison.png")

    print("\nAll charts generated successfully!")
