// 与 Python 共用 channels.json；每个页面通过 ?channel=male|female 保持频道。
window.RankChannels = (() => {
    let pending = null;

    function init() {
        if (!pending) pending = load();
        return pending;
    }

    async function load() {
        const response = await fetch(`channels.json?v=${Math.floor(Date.now() / 600000)}`);
        if (!response.ok) throw new Error('频道配置加载失败');
        const configs = await response.json();
        const requested = new URLSearchParams(window.location.search).get('channel');
        const id = Object.hasOwn(configs, requested) ? requested : 'female';
        const config = configs[id];
        if (!config) throw new Error('频道配置无效');
        const channel = {
            ...config,
            id,
            dataPath: file => `${config.data_dir}/${file}`,
            apiPath: file => `${config.api_dir}/${file}`,
            snapshotPath: date => `${config.data_dir}/${config.snapshot_prefix}${date.replace(/-/g, '')}.json`,
            url: path => {
                const url = new URL(path, window.location.href);
                url.searchParams.set('channel', id);
                return `${url.pathname}${url.search}${url.hash}`;
            },
        };

        document.querySelectorAll('[data-channel-switch]').forEach(container => {
            Object.entries(configs).forEach(([key, item]) => {
                const link = document.createElement('a');
                const url = new URL(window.location.href);
                if (url.pathname.endsWith('/book.html')) {
                    url.pathname = url.pathname.replace(/book\.html$/, 'index.html');
                    url.search = '';
                }
                url.searchParams.set('channel', key);
                url.searchParams.delete('type');
                link.href = `${url.pathname}${url.search}`;
                link.textContent = item.label;
                if (key === id) link.setAttribute('aria-current', 'page');
                container.appendChild(link);
            });
        });
        document.querySelectorAll('a[data-channel-link]').forEach(link => {
            link.href = channel.url(link.getAttribute('href'));
        });
        document.querySelectorAll('[data-channel-subtitle]').forEach(element => {
            element.textContent = `${config.label}新书榜追踪`;
        });
        document.title = document.title.replace('男女频', config.label);
        return channel;
    }

    return { init };
})();
