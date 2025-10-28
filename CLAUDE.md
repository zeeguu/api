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

## Tool Scripts Structure
- **All tool scripts that access the database MUST initialize Flask app context**
- **Required boilerplate at the top of every tool file** (after imports, before any database operations):

```python
from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()
```

- **Why**: SQLAlchemy requires Flask application context to perform database operations
- **When**: Any script in `tools/` that queries or modifies database models needs this
- **Where**: Place after all imports, before any code that uses `db.session` or model queries

Example:
```python
#!/usr/bin/env python
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# REQUIRED: Initialize Flask app context for database access
from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()

# Now safe to import and use models
from zeeguu.core.model.user import User
from zeeguu.core.model.language import Language

# Your tool code here...
users = User.query.all()  # This works because app context is initialized
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

## Source and Article Architecture
- **Source Model**: An abstraction layer that unifies all content types (Article, Video, etc.) in the system
- **source_id in Articles/Videos**: Each Article and Video has a `source_id` that links to its corresponding Source record
- **NOT about publishers**: The `source_id` is NOT referring to the publisher or website origin - it's a content entity abstraction
- **Purpose**: Enables unified tracking of user interactions across different content types (articles, videos) without duplicating activity tracking logic
- **User Activity Tracking**: `user_ignored_sources` tracks Source IDs that users repeatedly scroll past, providing behavioral filtering
- **Relationship**: One-to-one relationship between Article↔Source and Video↔Source (enforced by unique constraint on source_id)