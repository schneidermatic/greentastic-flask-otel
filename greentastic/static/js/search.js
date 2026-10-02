// Type-ahead for the navbar search: while the user types, ask /api/suggest and list the product names.
const input = document.getElementById('search-input');
const list = document.getElementById('search-suggestions');
let timer;

function showSuggestions(items) {
    list.replaceChildren(...items.map(item => {
        const li = document.createElement('li');
        li.className = 'list-group-item list-group-item-action';
        li.textContent = item.name;
        // mousedown fires before the input loses focus (blur would hide the list first)
        li.addEventListener('mousedown', () => { location.href = '/search?q=' + encodeURIComponent(item.name); });
        return li;
    }));
    list.classList.toggle('d-none', items.length === 0);
}

input.addEventListener('input', () => {
    clearTimeout(timer);  // wait until the user pauses typing for 200 ms
    timer = setTimeout(async () => {
        const text = input.value.trim();
        if (!text) return showSuggestions([]);
        const response = await fetch('/api/suggest?q=' + encodeURIComponent(text));
        showSuggestions(response.ok ? await response.json() : []);
    }, 200);
});

input.addEventListener('blur', () => showSuggestions([]));
