import datetime
import json

current_year = datetime.date.today().year
current_month = datetime.date.today().month
current_day = datetime.date.today().day


# compute learned and learning words per month after the given date which is 1 year ago
def compute_learner_stats_during_last_year(user):
    # initialize variables
    learning_stats = [0] * 12
    learned_stats = [0] * 12

    all_bookmarks = user.all_bookmarks()
    date_one_year_ago = datetime.datetime(current_year - 1, current_month, current_day)

    # start the loop through all bookmarks
    for bookmark in all_bookmarks:

        # when bookmark was started to be learn
        if bookmark.time > date_one_year_ago:
            index_month_when_start_learning = (int(bookmark.time.strftime("%m")) - current_month) % 12
            learning_stats[index_month_when_start_learning] += 1
        else:
            learning_stats[0] += 1

        # when bookmark was learned if it was learned
        was_bookmark_learned, time_when_bookmark_was_learned = bookmark.has_been_learned()
        if was_bookmark_learned:
            if time_when_bookmark_was_learned > date_one_year_ago:
                index_month_when_learned = (int(time_when_bookmark_was_learned.strftime("%m")) - current_month) % 12
                learned_stats[index_month_when_learned] += 1
            else:
                learning_stats[0] -= 1
                learned_stats[0] += 1

    # take into the account already learned and learning words before in the learning array
    learning_stats[0] -= learned_stats[0]
    for i in range(1, 12):
        learning_stats[i] += learning_stats[(i - 1)] - learned_stats[i]

    # for loop which makes learned curve cumulative
    index = 0
    for (index) in range(0, 11):
        learned_stats[index + 1] += learned_stats[index]
        index += 1

    return [learning_stats, learned_stats]


def data_to_json(learner_stats_after):
    #      "Status": "Learning",
    #      "words": "202",
    #      "date": "Jan 2016"
    learning_stats_after = learner_stats_after[0]
    learned_stats_after = learner_stats_after[1]

    result = ""
    for i in range(0, 12):
        entry_year = current_year
        entry_month = (current_month + i) % 12 + 1
        if current_month < entry_month:
            entry_year -= 1
        entry_date = datetime.datetime(entry_year, entry_month, 1)
        entry_date = str(entry_date.strftime("%b %Y"))
        result = result + "{\"name\": \"Learning\", \"amount\": \"" + str(
                learning_stats_after[i]) + "\", \"date\": \"" + entry_date + "\"},"
        result = result + "{\"name\": \"Learned\", \"amount\": \"" + str(
                learned_stats_after[i]) + "\", \"date\": \"" + entry_date + "\"},"

    result = "[" + result[:-1] + "]"
    return json.dumps(result)


def compute_learner_stats(user):
    # return the result array as json
    return data_to_json(compute_learner_stats_during_last_year(user))
