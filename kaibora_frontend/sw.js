/* Service Worker (sw.js) para o Guia Kaibora */

const CACHE_NAME = 'kaibora-cache-v1';
// Lista de todos os ficheiros que o seu app precisa para funcionar offline.
const FILES_TO_CACHE = [
    '/', // Redireciona para a página de login
    'login.html',
    'registrar.html',
    'login.css',
    'kaibora.html',
    'kaibora.css',
    'mapa_3d.xhtml',
    'static/gm.css',
    'static/x3dom.js',
    'static/x3dom.css',
    'static/icon.png'
];

// 1. Evento de Instalação: Salva todos os ficheiros no cache.
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[Service Worker] Abrindo cache e guardando ficheiros...');
                return cache.addAll(FILES_TO_CACHE);
            })
    );
});

// 2. Evento de Fetch (Busca): Intercepta pedidos de rede.
self.addEventListener('fetch', (event) => {
    // Se for um pedido de API (para o nosso backend), não guarde em cache.
    // Vá sempre à rede (online).
    if (event.request.url.includes('/api/')) {
        return event.respondWith(fetch(event.request));
    }

    // Se for um ficheiro do nosso app (HTML, CSS, JS), tente o cache primeiro.
    event.respondWith(
        caches.match(event.request)
            .then((response) => {
                // Se o ficheiro estiver no cache, retorna-o.
                if (response) {
                    return response;
                }
                // Se não estiver, busca na rede, salva no cache e retorna.
                return fetch(event.request).then((networkResponse) => {
                    return caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, networkResponse.clone());
                        return networkResponse;
                    });
                });
            })
            .catch(() => {
                // Se a rede falhar e não estiver no cache (ex: offline pela 1ª vez)
                // (Podemos retornar uma página "offline" aqui, mas por agora, apenas falha)
            })
    );
});