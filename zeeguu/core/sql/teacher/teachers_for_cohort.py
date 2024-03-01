from zeeguu.core.sql.query_building import list_of_dicts_from_query


def teachers_for_cohort(cohort_id):
    query = """
                select u.id as user_id, u.email, u.name
    
                from 
                    teacher_cohort_map as tcm
    
                    join user as u 
                        on u.id = tcm.user_id 
    
                where tcm.cohort_id = :cohort_id
            """

    return list_of_dicts_from_query(
        query,
        {"cohort_id": cohort_id},
    )
