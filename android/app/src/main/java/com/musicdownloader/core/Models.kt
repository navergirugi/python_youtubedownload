package com.musicdownloader.core

// Port of models.py
data class Candidate(
    val title: String,
    val url: String,
    val channel: String = "",
    val durationStr: String = ""
)
