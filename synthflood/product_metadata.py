"""Read real and synthetic rating fields without inventing missing evidence."""
import math


def rating_value(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and 0 <= number <= 5 else None


def review_count_value(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(str(value).strip().replace(',', ''))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        return None
    return int(number)


def rating_and_count(item):
    rating = None
    for key in ('Rating', 'average_rating', 'star5_ratios', 'rating'):
        rating = rating_value(item.get(key))
        if rating is not None:
            break
    count = None
    for key in ('num_reviews', 'review_num', 'total_reviews'):
        count = review_count_value(item.get(key))
        if count is not None:
            break
    return rating, count


def restore_raw_metadata(item, raw):
    """Return a copy with only canonical rating/count and raw count restored.

    Historical frozen items retain average_rating but lost total_reviews.
    The original raw product is the source of truth for this repair. It does
    not contain review bodies; a review count must never fabricate reviews.
    """
    restored = dict(item)
    rating = rating_value(raw.get('average_rating'))
    count = review_count_value(raw.get('total_reviews'))
    restored['Rating'] = rating if rating is not None else 'N.A.'
    restored['num_reviews'] = count
    restored['total_reviews'] = raw.get('total_reviews')
    return restored
