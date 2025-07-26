# Project Configuration for Claude

## Python Environment
- **Always use the virtual environment**: `~/.venvs/z_env`
- **Python commands should be prefixed with**: `source ~/.venvs/z_env/bin/activate && `

## Examples:
```bash
# Running Python scripts
source ~/.venvs/z_env/bin/activate && python -m tools._playground

# Running tests
source ~/.venvs/z_env/bin/activate && python -m pytest

# Any Python-related command
source ~/.venvs/z_env/bin/activate && python <command>
```

## Database Migrations
- **Migrations are SQL scripts, NOT Alembic**: Do not use `alembic revision`
- **Migration location**: Place all migration scripts in `tools/migrations/` folder
- **Naming convention**: `YY-MM-DD--description.sql` (e.g., `25-07-07--add_meaning_frequency.sql`)
  - YY: Two-digit year
  - MM: Two-digit month  
  - DD: Two-digit day
  - Double dash followed by descriptive name in lowercase with underscores
- **Multiple migrations per day**: Use letter suffixes -a, -b, -c, etc. to maintain order
  - Example: `25-07-08-a--add_phrase_type.sql`, `25-07-08-b--add_multi_word.sql`
- **Format**: Plain SQL files (.sql extension)

Example:
```sql
-- tools/migrations/25-07-07--add_meaning_frequency.sql
ALTER TABLE meaning 
ADD COLUMN frequency ENUM('unique', 'common', 'uncommon', 'rare') 
DEFAULT NULL 
COMMENT 'How frequently this particular meaning is used';
```

## Project Context
This is the Zeeguu API project which requires the z_env virtual environment to run properly due to specific dependencies and configurations.

## Word Scheduling System
- **Single Table Inheritance**: `FourLevelsPerWord` inherits from `BasicSRSchedule` and uses the same database table (`basic_sr_schedule`)
- **Use BasicSRSchedule for ALL database queries**: Since there's only one table, always use `BasicSRSchedule` for joins, filters, and query methods
- **Use FourLevelsPerWord ONLY for creating instances**: When creating new schedule entries, use `FourLevelsPerWord.find_or_create()` not `BasicSRSchedule.find_or_create()` (which raises NotImplementedError)
- **Examples**: 
  ```python
  # ✓ Correct - use BasicSRSchedule for database queries
  .outerjoin(BasicSRSchedule, BasicSRSchedule.user_word_id == UserWord.id)
  .filter(BasicSRSchedule.id == None)
  count = BasicSRSchedule.scheduled_user_words_count(user)
  
  # ✓ Correct - use concrete implementation for creation
  schedule = FourLevelsPerWord.find_or_create(db.session, user_word)
  
  # ✗ Wrong - FourLevelsPerWord doesn't have its own table
  .outerjoin(FourLevelsPerWord, FourLevelsPerWord.user_word_id == UserWord.id)
  
  # ✗ Wrong - will raise NotImplementedError
  schedule = BasicSRSchedule.find_or_create(db.session, user_word)
  ```