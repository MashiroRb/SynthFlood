"""Verbatim port of the official WebShop product loader.

Source: webshop_repo/web_agent_site/engine/engine.py
        (clean_product_keys, generate_product_prices, load_products)
The only changes: file paths are parameters (not module constants) and the
pyserini/flask imports are dropped. Loading must be byte-identical to the
official pipeline so that goals and rewards match the benchmark.
"""
import json
import os
import pickle
import random
import re
from collections import defaultdict
from decimal import Decimal

from tqdm import tqdm


def clean_product_keys(products):
    for product in products:
        product.pop('product_information', None)
        product.pop('brand', None)
        product.pop('brand_url', None)
        product.pop('list_price', None)
        product.pop('availability_quantity', None)
        product.pop('availability_status', None)
        product.pop('total_reviews', None)
        product.pop('total_answered_questions', None)
        product.pop('seller_id', None)
        product.pop('seller_name', None)
        product.pop('fulfilled_by_amazon', None)
        product.pop('fast_track_message', None)
        product.pop('aplus_present', None)
        product.pop('small_description_old', None)
    return products


def generate_product_prices(all_products, seed=2027):
    rng = random.Random(seed)
    product_prices = dict()
    for product in all_products:
        asin = product['asin']
        pricing = product['pricing']
        if not pricing:
            price = 100.0
        elif len(pricing) == 1:
            price = pricing[0]
        else:
            price = rng.uniform(*pricing[:2])
        product_prices[asin] = price
    return product_prices


def load_products(filepath, attr_path, human_attr_path, num_products=None,
                  human_goals=True):
    with open(filepath) as f:
        products = json.load(f)
    print(f'Products loaded: {len(products)}')
    products = clean_product_keys(products)

    all_reviews = dict()
    all_ratings = dict()

    with open(attr_path) as f:
        attributes = json.load(f)
    if human_goals:
        with open(human_attr_path) as f:
            human_attributes = json.load(f)
    print('Attributes loaded.')

    asins = set()
    all_products = []
    attribute_to_asins = defaultdict(set)
    if num_products is not None:
        products = products[:num_products]
    for i, p in tqdm(enumerate(products), total=len(products)):
        asin = p['asin']
        if asin == 'nan' or len(asin) > 10:
            continue

        if asin in asins:
            continue
        else:
            asins.add(asin)

        products[i]['category'] = p['category']
        products[i]['query'] = p['query']
        products[i]['product_category'] = p['product_category']

        products[i]['Title'] = p['name']
        products[i]['Description'] = p['full_description']
        products[i]['Reviews'] = all_reviews.get(asin, [])
        products[i]['Rating'] = all_ratings.get(asin, 'N.A.')
        for r in products[i]['Reviews']:
            if 'score' not in r:
                r['score'] = r.pop('stars')
            if 'review' not in r:
                r['body'] = ''
            else:
                r['body'] = r.pop('review')
        products[i]['BulletPoints'] = p['small_description'] \
            if isinstance(p['small_description'], list) else [p['small_description']]

        pricing = p.get('pricing')
        if pricing is None or not pricing:
            pricing = [100.0]
            price_tag = '$100.0'
        else:
            pricing = [
                float(Decimal(re.sub(r'[^\d.]', '', price)))
                for price in pricing.split('$')[1:]
            ]
            if len(pricing) == 1:
                price_tag = f"${pricing[0]}"
            else:
                price_tag = f"${pricing[0]} to ${pricing[1]}"
                pricing = pricing[:2]
        products[i]['pricing'] = pricing
        products[i]['Price'] = price_tag

        options = dict()
        customization_options = p['customization_options']
        option_to_image = dict()
        if customization_options:
            for option_name, option_contents in customization_options.items():
                if option_contents is None:
                    continue
                option_name = option_name.lower()

                option_values = []
                for option_content in option_contents:
                    option_value = option_content['value'].strip().replace('/', ' | ').lower()
                    option_image = option_content.get('image', None)

                    option_values.append(option_value)
                    option_to_image[option_value] = option_image
                options[option_name] = option_values
        products[i]['options'] = options
        products[i]['option_to_image'] = option_to_image

        if asin in attributes and 'attributes' in attributes[asin]:
            products[i]['Attributes'] = attributes[asin]['attributes']
        else:
            products[i]['Attributes'] = ['DUMMY_ATTR']

        if human_goals:
            if asin in human_attributes:
                products[i]['instructions'] = human_attributes[asin]
        else:
            products[i]['instruction_text'] = \
                attributes[asin].get('instruction', None)

            products[i]['instruction_attributes'] = \
                attributes[asin].get('instruction_attributes', None)

        products[i]['MainImage'] = p['images'][0]
        products[i]['query'] = p['query'].lower().strip()

        all_products.append(products[i])

    for p in all_products:
        for a in p['Attributes']:
            attribute_to_asins[a].add(p['asin'])

    product_item_dict = {p['asin']: p for p in all_products}
    product_prices = generate_product_prices(all_products)
    return all_products, product_item_dict, product_prices, attribute_to_asins


def load_official_data(data_dir, cache=True):
    """Load via the verbatim port, with a pickle cache (json.load of the
    5.5GB items_shuffle.json takes several minutes)."""
    if os.environ.get("SYNTHFLOOD_PRODUCT_CACHE") == "0":
        cache = False
    # Old caches contain an unseeded price table; do not silently reuse them.
    cache_path = os.path.join(data_dir, "all_products_prices2027_v2.pkl")
    if cache and os.path.exists(cache_path):
        print(f"loading cached products from {cache_path}")
        with open(cache_path, "rb") as f:
            return pickle.load(f)
    out = load_products(
        filepath=os.path.join(data_dir, "items_shuffle.json"),
        attr_path=os.path.join(data_dir, "items_ins_v2.json"),
        human_attr_path=os.path.join(data_dir, "items_human_ins.json"))
    if cache:
        with open(cache_path, "wb") as f:
            pickle.dump(out, f, protocol=4)
    return out
