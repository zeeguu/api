from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.model.cohort import Cohort
from zeeguu.core.model.teacher_cohort_map import TeacherCohortMap


class CohortRule(BaseRule):
    """
        A cohort has a teacher and a bunch of students
    """

    def __init__(self):
        super().__init__()
        self.cohort = self._create_model_object()
        self.save(self.cohort)

        self.teacher = UserRule().user
        self.save(self.teacher)

        teacher_role = TeacherCohortMap(self.teacher, self.cohort)
        self.save(teacher_role)

        self.student1 = UserRule().user
        self.student1.cohort = self.cohort
        self.save(self.student1)

        student2 = UserRule().user
        student2.cohort = self.cohort
        self.save(student2)

    def _create_model_object(self, *args):
        name = self.faker.word()
        inv_code = self.faker.word()
        max_students = 10
        language = LanguageRule().random
        cohort = Cohort(inv_code,name, language, max_students)

        return cohort

    @staticmethod
    def _exists_in_db(obj):
        return Cohort.find(obj.id)
