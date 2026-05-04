<script>
    import { onMount } from "svelte";
    import ReaderPage from "./ReaderPage.svelte";

    const API_BASE = "http://127.0.0.1:8080";

    let homeData = null;
    let search = "";
    let sort = "alphabetical";
    let loading = true;
    let error = "";
    let page = window.location.pathname;

    let showSettings = false;

    let visibleSections = {
        favorites: true,
        recently_read: true,
        recently_updated: true,
        archived: false,
        all_comics: true,
    };

    window.addEventListener("popstate", () => {
        page = window.location.pathname;
    });

    async function loadHome() {
        loading = true;
        error = "";

        try {
            const params = new URLSearchParams({ search, sort });
            const res = await fetch(`${API_BASE}/api/home?${params}`);

            if (!res.ok) throw new Error(`API error: ${res.status}`);

            homeData = await res.json();
        } catch (err) {
            error = err.message;
        } finally {
            loading = false;
        }
    }

    function coverUrl(comic) {
        return comic.cover_url ? `${API_BASE}${comic.cover_url}` : "";
    }

    async function toggleFavorite(comic) {
        await fetch(`${API_BASE}/api/comics/${encodeURIComponent(comic.name)}/favorite`, {
            method: "PATCH",
        });

        await loadHome();
    }

    async function toggleArchive(comic) {
        await fetch(`${API_BASE}/api/comics/${encodeURIComponent(comic.name)}/archive`, {
            method: "PATCH",
        });

        await loadHome();
    }

    function goReader(comic) {
        const chapter = comic.current_chapter && comic.current_chapter !== "0"
            ? comic.current_chapter
            : "1";

        const url = `/reader?comic=${encodeURIComponent(comic.name)}&chapter=${encodeURIComponent(chapter)}`;

        window.history.pushState({}, "", url);
        page = "/reader";
    }

    onMount(() => {
        if (page !== "/reader") {
            loadHome();
        }
    });
</script>

{#if page === "/reader"}
    <ReaderPage />
{:else}
    <main>
        <header>
            <button class="settings-btn" on:click={() => showSettings = !showSettings}>
                ⚙ Settings
            </button>

            {#if showSettings}
                <div class="settings-panel">
                    {#each [
                        ["favorites", "Favorites"],
                        ["recently_read", "Recently Read"],
                        ["recently_updated", "Recently Updated"],
                        ["archived", "Archived"],
                        ["all_comics", "All Comics"],
                    ] as [key, label]}
                        <label>
                            <input type="checkbox" bind:checked={visibleSections[key]} />
                            {label}
                        </label>
                    {/each}
                </div>
            {/if}

            <h1>Athenaeum</h1>

            <div class="controls">
                <input
                    bind:value={search}
                    on:input={loadHome}
                    placeholder="Search comics..."
                />

                <select bind:value={sort} on:change={loadHome}>
                    <option value="alphabetical">Alphabetical</option>
                    <option value="chapters">Most chapters</option>
                    <option value="progress">Progress</option>
                </select>
            </div>
        </header>

        {#if loading}
            <p class="loading">Loading...</p>
        {:else if error}
            <p class="error">{error}</p>
        {:else}
            {#each [
                ["favorites", "Favorites", homeData.favorites],
                ["recently_read", "Recently Read", homeData.recently_read],
                ["recently_updated", "Recently Updated", homeData.recently_updated],
                ["archived", "Archived", homeData.all_comics.filter((comic) => comic.is_archived)],
                ["all_comics", "All Comics", homeData.all_comics],
            ] as [key, title, comics]}
                {#if visibleSections[key] && comics.length > 0}
                    <section>
                        <h2>{title}</h2>

                        <div class="grid">
                            {#each comics as comic}
                                <article class:archived={comic.is_archived}>
                                    <img src={coverUrl(comic)} alt={comic.name} />

                                    <h3>{comic.name}</h3>

                                    <p>
                                        {comic.read_chapters} / {comic.total_chapters}
                                        ({comic.progress_percentage}%)
                                    </p>

                                    <div class="buttons">
                                        <button class="read" on:click={() => goReader(comic)}>
                                            READ
                                        </button>

                                        <button class="circle" on:click={() => toggleFavorite(comic)}>
                                            {comic.is_favorite ? "♥" : "♡"}
                                        </button>

                                        <button class="circle" on:click={() => toggleArchive(comic)}>
                                            {comic.is_archived ? "🔒" : "🔓"}
                                        </button>
                                    </div>
                                </article>
                            {/each}
                        </div>
                    </section>
                {/if}
            {/each}
        {/if}
    </main>
{/if}

<style>
    main {
        width: 100%;
        min-height: 100vh;
        background: #111;
        color: white;
        padding: 32px;
        box-sizing: border-box;
        font-family: Arial, sans-serif;
    }

    header {
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        margin-bottom: 32px;
    }

    h1 {
        text-align: center;
        width: 100%;
        margin: 24px 0 20px;
        font-size: 42px;
        color: white;
    }

    h2 {
        text-align: center;
        margin-bottom: 16px;
        color: white;
    }

    .controls {
        width: 100%;
        max-width: 1400px;
        display: flex;
        gap: 16px;
    }

    .controls input,
    .controls select {
        background: #1d1d1d;
        color: white;
        border: 1px solid #333;
        border-radius: 12px;
        padding: 14px 18px;
        font-size: 16px;
        box-sizing: border-box;
        outline: none;
    }

    .controls input {
        flex: 1;
        min-width: 0;
    }

    .controls select {
        width: 240px;
        flex-shrink: 0;
    }

    .controls input::placeholder {
        color: #aaa;
    }

    .settings-btn {
        position: absolute;
        top: 0;
        right: 0;
        background: #1d1d1d;
        border: 1px solid #333;
        border-radius: 999px;
        padding: 10px 16px;
        color: white;
        cursor: pointer;
    }

    .settings-panel {
        position: absolute;
        top: 52px;
        right: 0;
        background: #1a1a1a;
        border: 1px solid #333;
        border-radius: 16px;
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        z-index: 20;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
    }

    .settings-panel label {
        display: flex;
        gap: 8px;
        align-items: center;
        color: white;
        white-space: nowrap;
        font-size: 14px;
    }

    section {
        margin-bottom: 48px;
    }

    .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
        gap: 24px;
    }

    article {
        background: #1a1a1a;
        border-radius: 18px;
        padding: 12px;
    }

    article img {
        width: 100%;
        aspect-ratio: 2 / 3;
        object-fit: cover;
        border-radius: 14px;
        background: #222;
    }

    article.archived img {
        filter: grayscale(1) brightness(0.45);
    }

    h3 {
        font-size: 15px;
        margin: 10px 0 4px;
        color: white;
    }

    p {
        color: #bbb;
        font-size: 13px;
        margin: 0 0 10px;
    }

    .buttons {
        display: flex;
        gap: 8px;
    }

    button {
        cursor: pointer;
        border: none;
        color: white;
    }

    .read {
        flex: 1;
        background: #d71920;
        border-radius: 999px;
        padding: 10px;
        font-weight: bold;
    }

    article.archived .read {
        filter: grayscale(1);
    }

    .circle {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        background: transparent;
        border: 1px solid #555;
        font-size: 18px;
    }

    .loading,
    .error {
        text-align: center;
        padding-top: 60px;
    }

    .error {
        color: #ff6666;
    }
</style>