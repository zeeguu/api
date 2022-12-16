# Example Queries

## Query only some fields from every document

```
    GET zeeguu/_search
        {
        "_source": ["title", "published_time", "topics", "_score"],
        "size":20.0,
        "query" : {
                "terms" : {
                    "topics" : ["music", "politics",  "business",  "food", "science", "technology"]
                }
            }
        }
```

## Query Using Terms

- terms has to be lowercase
- it still happens that if I add more topics in terms I get less results - even if it's supposed to do an OR between them

```
{
   "size":20.0,
   "query":{
      "function_score":{
         "functions":[
            {
               "gauss":{
                  "published_time":{
                     "scale":"365d",
                     "offset":"7d",
                     "decay":0.3
                  }
               },
               "weight":1.2
            }
         ],
         "query":{
            "bool":{
               "filter":{
                  "range":{
                     "fk_difficulty":{
                        "gt":10,
                        "lt":55.0
                     }
                  }
               },
               "must":[
                  {
                     "match":{
                        "language":"French"
                     }
                  },
                  {
                     "exists":{
                        "field":"published_time"
                     }
                  },
                  {
                     "terms":{
                        "topics":[
                           "culture",
                           "music",
                           "politics",
                           "food",
                           "health",
                           "science",
                           "world",
                           "travel",
                           "technology",
                           "business"
                        ]
                     }
                  }
               ],
               "must_not":[
                  {
                     "match":{
                        "topics":"Sport"
                     }
                  },
                  {
                     "match":{
                        "content":"FC"
                     }
                  },
                  {
                     "match":{
                        "title":"FC"
                     }
                  }
               ]
            }
         }
      }
   }
}
```

## The Query Deployed till Nov 2022

```
GET zeeguu/_search
{
  "_source": ["title", "published_time", "topics", "_score"],
   "size":20.0,

   "query":{
      "function_score":{
         "functions":[
            {
               "gauss":{
                  "published_time":{
                     "scale":"365d",
                     "offset":"7d",
                     "decay":0.3
                  }
               },
               "weight":3.2
            }
         ],
         "query":{
            "bool":{
               "filter":{
                  "range":{
                     "fk_difficulty":{
                        "gt":10,
                        "lt":55.0
                     }
                  }
               },
               "should":[
                  {
                     "match":{
                        "topics":"Culture"
                     }
                  },
                  {
                     "match":{
                        "topics":"Music"
                     }
                  }
               ],
               "must":[
                  {
                     "match":{
                        "language":"French"
                     }
                  },
                  {
                     "exists":{
                        "field":"published_time"
                     }
                  }
               ],
               "must_not":[
                  {
                     "match":{
                        "topics":"Sport"
                     }
                  },
                  {
                     "match":{
                        "content":"FC"
                     }
                  },
                  {
                     "match":{
                        "title":"FC"
                     }
                  }
               ]
            }
         }
      }
   }
}



```
