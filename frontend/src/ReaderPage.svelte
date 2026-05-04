<script>
    import { onMount } from "svelte";

    const API_BASE = "http://127.0.0.1:8080";

    let comicName = "";
    let chapterNum = "";
    let chapterData = null;
    let loading = true;
    let error = "";

    async function loadChapter() {
        loading = true;
        error = "";

        const params = new URLSearchParams(window.location.search);
        comicName = params.get("comic") || "";
        chapterNum = params.get("chapter") || "1";

        try {
            const res = await fetch(
                `${API_BASE}/api/comics/${encodeURIComponent(comicName)}/chapters/${encodeURIComponent(chapterNum)}`
            );

            if (!res.ok) throw new Error(`API error: ${res.status}`);

            chapterData = await res.json();

            await fetch(`${API_BASE}/api/progress/${encodeURIComponent(comicName)}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ chapter_num: chapterNum }),
            });
        } catch (err) {
            error = err.message;
        } finally {
            loading = false;
        }
    }

    function goHome() {
        window.location.href = "/";
    }

    function goChapter(chapter) {
        window.location.href = `/reader?comic=${encodeURIComponent(comicName)}&chapter=${encodeURIComponent(chapter)}`;
    }

    function getCurrentIndex() {
        return chapterData.chapters.indexOf(chapterData.chapter_num);
    }

    function prevChapter() {
        const index = getCurrentIndex();
        if (index > 0) goChapter(chapterData.chapters[index - 1]);
    }

    function nextChapter() {
        if (chapterData.next_chapter) {
            goChapter(chapterData.next_chapter);
        } else {
            goHome();
        }
    }

    onMount(loadChapter);
</script>

<main>
    {#if loading}
        <p class="loading">Loading chapter...</p>
    {:else if error}
        <p class="error">{error}</p>
    {:else}
        <header>
            <button class="back" on:click={goHome}>Back</button>

            <h1>{chapterData.comic_name}</h1>
            <h2>Chapter {chapterData.chapter_num}</h2>

            <div class="chapter-controls">
                <button on:click={prevChapter} disabled={getCurrentIndex() === 0}>
                    &lt; Prev
                </button>

                <select bind:value={chapterNum} on:change={(e) => goChapter(e.target.value)}>
                    {#each chapterData.chapters as chapter}
                        <option value={chapter}>Chapter {chapter}</option>
                    {/each}
                </select>

                <button on:click={nextChapter}>
                    {chapterData.is_latest_chapter ? "Home" : "Next >"}
                </button>
            </div>
        </header>

        <div class="pages">
            {#each chapterData.images as img}
                <img src={`${API_BASE}${img}`} alt="" draggable="false" />
            {/each}
        </div>

        <button class="next-big" on:click={nextChapter}>
            {chapterData.is_latest_chapter ? "GO HOME" : "NEXT CHAPTER"}
        </button>
    {/if}
</main>

<style>
    main {
        min-height: 100vh;
        background: #111;
        color: white;
        padding: 24px;
        box-sizing: border-box;
        text-align: center;
    }

    header {
        max-width: 900px;
        margin: 0 auto 24px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 14px;
    }

    h1 {
        color: white;
        font-size: 42px;
        margin: 16px 0 0;
    }

    h2 {
        color: #bbb;
        font-size: 22px;
        margin: 0;
    }

    .back {
        align-self: center;
        background: transparent;
        color: white;
        border: 1px solid #555;
        border-radius: 999px;
        padding: 10px 24px;
        cursor: pointer;
    }

    .chapter-controls {
        display: flex;
        gap: 10px;
        justify-content: center;
        align-items: center;
        flex-wrap: wrap;
        margin-top: 8px;
    }

    button,
    select {
        background: #1d1d1d;
        color: white;
        border: 1px solid #444;
        border-radius: 999px;
        padding: 10px 16px;
        cursor: pointer;
    }

    select {
        min-width: 180px;
        border-radius: 12px;
    }

    button:disabled {
        opacity: 0.35;
        cursor: not-allowed;
    }

    .pages {
        max-width: 900px;
        margin: 0 auto;
    }

    .pages img {
        display: block;
        width: 100%;
        margin: 0 auto;
        user-select: none;
    }

    .next-big {
        display: block;
        width: min(900px, 100%);
        margin: 32px auto;
        background: #d71920;
        border: none;
        border-radius: 14px;
        padding: 18px;
        font-weight: bold;
        cursor: pointer;
    }

    .loading,
    .error {
        text-align: center;
        padding-top: 80px;
    }

    .error {
        color: #ff6666;
    }
</style>