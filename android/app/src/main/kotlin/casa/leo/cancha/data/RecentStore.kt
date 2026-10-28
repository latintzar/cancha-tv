package casa.leo.cancha.data

import android.content.Context

/** Persists watch history: recientes (order) + tu más visto (counts) + favoritos. Survives restarts. */
object RecentStore {
    private const val PREF = "cancha_prefs"
    private const val KEY = "recent_channels"
    private const val KEY_COUNTS = "watch_counts"
    private const val KEY_FAVS = "favorites"
    private const val KEY_UPD_PROMPT = "update_prompted_code"
    private const val MAX = 14

    /** Highest versionCode we've already auto-offered, so we never re-nag for the same build. */
    fun lastUpdatePrompt(context: Context): Int =
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE).getInt(KEY_UPD_PROMPT, 0)

    fun setUpdatePrompted(context: Context, code: Int) {
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
            .edit().putInt(KEY_UPD_PROMPT, code).apply()
    }

    fun favIds(context: Context): List<String> {
        val sp = context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
        return sp.getString(KEY_FAVS, "")?.split(",")?.filter { it.isNotBlank() } ?: emptyList()
    }

    fun isFav(context: Context, id: String): Boolean = favIds(context).contains(id)

    /** Toggle favorite; returns the new state (true = now favorite). */
    fun toggleFav(context: Context, id: String): Boolean {
        val sp = context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
        val cur = favIds(context).toMutableList()
        val nowFav: Boolean
        if (cur.contains(id)) { cur.remove(id); nowFav = false } else { cur.add(0, id); nowFav = true }
        sp.edit().putString(KEY_FAVS, cur.joinToString(",")).apply()
        return nowFav
    }

    fun add(context: Context, id: String) {
        val sp = context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
        val cur = ids(context).toMutableList()
        cur.remove(id)
        cur.add(0, id)
        while (cur.size > MAX) cur.removeAt(cur.size - 1)
        // bump watch count
        val counts = countsMap(context).toMutableMap()
        counts[id] = (counts[id] ?: 0) + 1
        sp.edit()
            .putString(KEY, cur.joinToString(","))
            .putString(KEY_COUNTS, counts.entries.joinToString(",") { "${it.key}:${it.value}" })
            .apply()
    }

    fun ids(context: Context): List<String> {
        val sp = context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
        return sp.getString(KEY, "")?.split(",")?.filter { it.isNotBlank() } ?: emptyList()
    }

    private fun countsMap(context: Context): Map<String, Int> {
        val sp = context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
        return (sp.getString(KEY_COUNTS, "") ?: "").split(",").mapNotNull {
            val p = it.split(":"); if (p.size == 2) p[0] to (p[1].toIntOrNull() ?: 0) else null
        }.toMap()
    }

    /** Ids watched >= 2 times, most-first. */
    fun mostWatched(context: Context): List<String> =
        countsMap(context).filter { it.value >= 2 }.entries.sortedByDescending { it.value }.map { it.key }
}
