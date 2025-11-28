# Nice Decisions

This document records design decisions that turned out to be particularly clever or beneficial, often in ways that weren't immediately obvious.

## 1. Round-Trip AI Generator ID as Implicit Voting System

**Decision:** Frontend sends back `ai_generator_id` when saving chosen example sentences.

**Initially seemed like:** Awkward round-trip overhead - why not just store it on the backend?

**Actually brilliant because:** Creates an implicit voting/selection system where every saved ExampleSentence represents user validation.

### The Hidden Value

**Every ExampleSentence in the database represents:**
- ✅ **User validation** - A real user chose this sentence over alternatives
- ✅ **Quality signal** - It was good enough to be selected
- ✅ **Generator attribution** - We know which AI model/prompt created it

**This enables powerful analytics:**
- **Generator performance**: "Which AI models produce sentences users actually choose?"
- **Quality metrics**: "What's the selection rate for different generators?"
- **A/B testing**: "Does GPT-4 vs Claude produce better examples for Danish learners?"
- **Prompt optimization**: "Which prompt versions lead to more selections?"

**Future possibilities:**
- **Recommendation system**: "This generator created examples you liked before"
- **Quality ranking**: Show the most-selected examples first when browsing
- **Generator improvement**: Feedback loop to improve less-selected generators
- **Analytics dashboard**: "Your AI generators' success rates"

**Why this beats auto-saving all examples:**
- No database bloat with unused examples
- Clear quality signal - can distinguish good from bad
- Captures user preference data
- Easy to identify successful patterns

**Lesson:** What looks like implementation overhead can actually be valuable user behavior data in disguise. 🎯