-- Demo catalogue, only inserted into an empty products table. Images: static/<category>/<image>, see static/CREDITS.md.
INSERT INTO products (category, name, description, price, stock, unit, image)
SELECT * FROM (VALUES
    ('fruits',     'Apple',           'Fresh crisp apples',       2.50,  50, 'kg',  'AP.jpg'),
    ('fruits',     'Banana',          'Ripe sweet bananas',       1.80,  80, 'kg',  'banana.jpeg'),
    ('fruits',     'Guava',           'Juicy guavas',             3.90,  40, 'kg',  'guava.jpg'),
    ('fruits',     'Litchi',          'Seasonal litchis',         6.90,  30, 'kg',  'litchi.jpg'),
    ('fruits',     'Mango',           'Sweet alphonso mangoes',   3.50,  60, 'kg',  'mango.jpg'),
    ('fruits',     'Orange',          'Tangy oranges',            2.20,  70, 'kg',  'orange.jpg'),
    ('fruits',     'Pineapple',       'Fresh pineapples',         2.90,  25, 'kg',  'pineapple.jpg'),
    ('fruits',     'Pomegranate',     'Ruby red pomegranates',    4.50,  35, 'kg',  'pomogranate.png'),
    ('fruits',     'Strawberry',      'Hand-picked strawberries', 5.90,  20, 'kg',  'strawberry.jpg'),
    ('fruits',     'Watermelon',      'Large juicy watermelons',  1.20,  90, 'kg',  'watermelon.jpg'),
    ('vegetables', 'Broccoli',        'Fresh green broccoli',     2.80,  30, 'kg',  'broccolli.jpg'),
    ('vegetables', 'Cabbage',         'Crunchy cabbage',          1.10,  50, 'kg',  'cabbage.jpg'),
    ('vegetables', 'Chilli',          'Hot chillies',             7.50,  20, 'kg',  'chilli.jpg'),
    ('vegetables', 'Cucumber',        'Cool cucumbers',           1.00,  45, 'kg',  'cucumber.jpg'),
    ('vegetables', 'Garlic',          'Aromatic garlic',          8.90,  25, 'kg',  'garlic.jpg'),
    ('vegetables', 'Potato',          'Farm potatoes',            1.20, 100, 'kg',  'potato.jpg'),
    ('handmade',   'Candies',         'Homemade candies',         3.50,  40, 'pcs', 'candies.jpg'),
    ('handmade',   'Chocolates',      'Handmade chocolates',      6.90,  30, 'pcs', 'choci.jpg'),
    ('handmade',   'Cookies',         'Freshly baked cookies',    4.50,  50, 'pcs', 'cookies.jpg'),
    ('handmade',   'Cupcakes',        'Decorated cupcakes',       8.00,  24, 'pcs', 'cupcakes.jpg'),
    ('handmade',   'Scented Candle',  'Hand-poured scented candle', 12.90, 15, 'pcs', 'lavcandle.jpg'),
    ('handmade',   'Soap',            'Natural handmade soap',    5.50,  20, 'pcs', 'lavender.jpg'),
    ('handmade',   'Pickles',         'Traditional pickles',      4.90,  35, 'pcs', 'pickles.jpg'),
    ('handmade',   'Turmeric',        'Pure ground turmeric',     3.20,  45, 'pcs', 'turmeric.jpeg'),
    ('handcraft',  'Bamboo Cup',      'Carved bamboo cup',        9.90,  20, 'pcs', 'bamboocup.jpg'),
    ('handcraft',  'Clay Pot',        'Hand-moulded clay pot',   14.90,  15, 'pcs', 'claypot.jpg'),
    ('handcraft',  'Dream Catcher',   'Woven dream catcher',     12.00,  25, 'pcs', 'dreamcatcher.jpg'),
    ('handcraft',  'Purse',           'Embroidered fabric purse', 39.00, 10, 'pcs', 'handbags.jpg'),
    ('handcraft',  'Wood Carving',    'Carved wooden decor',     19.90,  12, 'pcs', 'wooden.jpeg')
) AS demo
WHERE NOT EXISTS (SELECT 1 FROM products);
