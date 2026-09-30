#include "mp3convert.h"

#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libavutil/audio_fifo.h>
#include <libavutil/channel_layout.h>
#include <libavutil/opt.h>
#include <libavutil/samplefmt.h>
#include <libswresample/swresample.h>

/* Return codes: 0 ok, 1 no audio stream, 2 encoder missing, 3 I/O error,
 * negative = libav error code. */

static enum AVSampleFormat pick_fmt(const AVCodec *enc) {
    if (enc->sample_fmts) {
        int i;
        for (i = 0; enc->sample_fmts[i] != AV_SAMPLE_FMT_NONE; i++) {
            if (enc->sample_fmts[i] == AV_SAMPLE_FMT_S16P)
                return AV_SAMPLE_FMT_S16P;
        }
        return enc->sample_fmts[0];
    }
    return AV_SAMPLE_FMT_S16P;
}

static int pick_rate(const AVCodec *enc, int src_rate) {
    if (enc->supported_samplerates) {
        int i, best = 0;
        for (i = 0; enc->supported_samplerates[i]; i++) {
            int r = enc->supported_samplerates[i];
            if (r <= src_rate && r > best)
                best = r;
        }
        if (best)
            return best;
        return enc->supported_samplerates[0];
    }
    return src_rate > 0 ? src_rate : 44100;
}

/* One encoded-ready frame (or flush with fr == NULL) through the encoder. */
static int encode_frame(AVCodecContext *enc, AVFrame *fr,
                        AVFormatContext *ofmt, int stream_idx) {
    int rc = avcodec_send_frame(enc, fr);
    if (rc < 0)
        return rc;
    for (;;) {
        AVPacket *p = av_packet_alloc();
        if (!p)
            return AVERROR(ENOMEM);
        rc = avcodec_receive_packet(enc, p);
        if (rc == AVERROR(EAGAIN) || rc == AVERROR_EOF) {
            av_packet_free(&p);
            break;
        }
        if (rc < 0) {
            av_packet_free(&p);
            return rc;
        }
        av_packet_rescale_ts(p, enc->time_base,
                             ofmt->streams[stream_idx]->time_base);
        p->stream_index = stream_idx;
        rc = av_interleaved_write_frame(ofmt, p);
        av_packet_free(&p);
        if (rc < 0)
            return rc;
    }
    return 0;
}

/* libmp3lame demands exactly frame_size (1152) samples on every
 * non-final frame, so resampled output goes through a fifo and only
 * full frames are sent mid-stream. The tail remainder is sent once
 * at the very end as the final frame. */
static int encode_fifo(AVAudioFifo *fifo, AVCodecContext *enc,
                       AVFormatContext *ofmt, int stream_idx,
                       int64_t *next_pts, int final) {
    int frame_size = enc->frame_size > 0 ? enc->frame_size : 1152;
    int channels = enc->ch_layout.nb_channels;

    for (;;) {
        int avail = av_audio_fifo_size(fifo);
        int chunk, rc;
        AVFrame *sub;

        if (avail <= 0)
            return 0;
        if (avail < frame_size && !final)
            return 0;
        chunk = avail < frame_size ? avail : frame_size;
        sub = av_frame_alloc();
        if (!sub)
            return AVERROR(ENOMEM);
        if (av_channel_layout_copy(&sub->ch_layout, &enc->ch_layout) < 0) {
            av_frame_free(&sub);
            return -1;
        }
        sub->sample_rate = enc->sample_rate;
        sub->format = enc->sample_fmt;
        sub->nb_samples = chunk;
        if (av_frame_get_buffer(sub, 0) < 0) {
            av_frame_free(&sub);
            return -1;
        }
        if (av_audio_fifo_read(fifo, (void **)sub->data, chunk) < chunk) {
            av_frame_free(&sub);
            return -1;
        }
        sub->pts = *next_pts;
        *next_pts += chunk;
        rc = encode_frame(enc, sub, ofmt, stream_idx);
        av_frame_free(&sub);
        if (rc < 0)
            return rc;
    }
}

/* Resample one decoded frame (NULL flushes delay) into the fifo. */
static int resample_frame(SwrContext *swr, AVCodecContext *enc, AVFrame *dec,
                          AVAudioFifo *fifo) {
    AVFrame *out = NULL;
    int rc;

    out = av_frame_alloc();
    if (!out)
        return AVERROR(ENOMEM);
    if (av_channel_layout_copy(&out->ch_layout, &enc->ch_layout) < 0) {
        av_frame_free(&out);
        return -1;
    }
    out->sample_rate = enc->sample_rate;
    out->format = enc->sample_fmt;
    out->nb_samples = swr_get_out_samples(swr, dec ? dec->nb_samples : 0);
    if (out->nb_samples <= 0) {
        av_frame_free(&out);
        return 0;
    }
    if (av_frame_get_buffer(out, 0) < 0) {
        av_frame_free(&out);
        return -1;
    }
    rc = swr_convert_frame(swr, out, dec);
    if (rc < 0) {
        av_frame_free(&out);
        return rc;
    }
    if (out->nb_samples == 0) {
        av_frame_free(&out);
        return 0;
    }
    if (av_audio_fifo_write(fifo, (void **)out->data, out->nb_samples)
        < out->nb_samples) {
        av_frame_free(&out);
        return -1;
    }
    av_frame_free(&out);
    return 0;
}

int mdl_convert_to_mp3(const char *src_path, const char *dst_path,
                       int bitrate_kbps) {
    AVFormatContext *ifmt = NULL, *ofmt = NULL;
    AVCodecContext *dec_ctx = NULL, *enc_ctx = NULL;
    SwrContext *swr = NULL;
    AVAudioFifo *fifo = NULL;
    AVFrame *dec_frame = NULL;
    AVPacket *pkt = NULL;
    AVStream *in_stream = NULL;
    int audio_idx = -1, stream_idx = 0, rc;
    int64_t next_pts = 0;

    if (!src_path || !dst_path || bitrate_kbps <= 0)
        return 3;
    if (avformat_open_input(&ifmt, src_path, NULL, NULL) < 0)
        return 3;
    if ((rc = avformat_find_stream_info(ifmt, NULL)) < 0)
        goto end;
    rc = av_find_best_stream(ifmt, AVMEDIA_TYPE_AUDIO, -1, -1, NULL, 0);
    if (rc < 0) {
        rc = 1;
        goto end;
    }
    audio_idx = rc;
    in_stream = ifmt->streams[audio_idx];
    (void)in_stream;

    {
        const AVCodec *dec = avcodec_find_decoder(
            ifmt->streams[audio_idx]->codecpar->codec_id);
        if (!dec) {
            rc = 1;
            goto end;
        }
        dec_ctx = avcodec_alloc_context3(dec);
        if (!dec_ctx) {
            rc = 3;
            goto end;
        }
        if ((rc = avcodec_parameters_to_context(
                 dec_ctx, ifmt->streams[audio_idx]->codecpar)) < 0)
            goto end;
        if ((rc = avcodec_open2(dec_ctx, dec, NULL)) < 0)
            goto end;
    }

    {
        const AVCodec *enc = avcodec_find_encoder_by_name("libmp3lame");
        if (!enc) {
            rc = 2;
            goto end;
        }
        enc_ctx = avcodec_alloc_context3(enc);
        if (!enc_ctx) {
            rc = 3;
            goto end;
        }
        enc_ctx->bit_rate = (int64_t)bitrate_kbps * 1000;
        enc_ctx->sample_rate = pick_rate(enc, dec_ctx->sample_rate);
        if (dec_ctx->ch_layout.nb_channels > 0) {
            if ((rc = av_channel_layout_copy(&enc_ctx->ch_layout,
                                             &dec_ctx->ch_layout)) < 0)
                goto end;
        } else {
            av_channel_layout_default(&enc_ctx->ch_layout, 2);
        }
        enc_ctx->sample_fmt = pick_fmt(enc);
        enc_ctx->time_base = (AVRational){1, enc_ctx->sample_rate};
        if ((rc = avcodec_open2(enc_ctx, enc, NULL)) < 0)
            goto end;
    }

    if (swr_alloc_set_opts2(&swr,
                            &enc_ctx->ch_layout, enc_ctx->sample_fmt,
                            enc_ctx->sample_rate,
                            &dec_ctx->ch_layout, dec_ctx->sample_fmt,
                            dec_ctx->sample_rate,
                            0, NULL) < 0) {
        rc = 3;
        goto end;
    }
    if ((rc = swr_init(swr)) < 0)
        goto end;

    fifo = av_audio_fifo_alloc(enc_ctx->sample_fmt,
                               enc_ctx->ch_layout.nb_channels, 1152 * 8);
    if (!fifo) {
        rc = 3;
        goto end;
    }

    if (avformat_alloc_output_context2(&ofmt, NULL, "mp3", dst_path) < 0 || !ofmt) {
        rc = 3;
        goto end;
    }
    {
        AVStream *out_stream = avformat_new_stream(ofmt, NULL);
        if (!out_stream) {
            rc = 3;
            goto end;
        }
        stream_idx = out_stream->index;
        if ((rc = avcodec_parameters_from_context(out_stream->codecpar,
                                                 enc_ctx)) < 0)
            goto end;
        out_stream->time_base = enc_ctx->time_base;
    }
    if (!(ofmt->oformat->flags & AVFMT_NOFILE)) {
        if ((rc = avio_open(&ofmt->pb, dst_path, AVIO_FLAG_WRITE)) < 0) {
            rc = 3;
            goto end;
        }
    }
    if ((rc = avformat_write_header(ofmt, NULL)) < 0)
        goto end;

    dec_frame = av_frame_alloc();
    pkt = av_packet_alloc();
    if (!dec_frame || !pkt) {
        rc = 3;
        goto end;
    }

    for (;;) {
        rc = av_read_frame(ifmt, pkt);
        if (rc == AVERROR_EOF)
            break;
        if (rc < 0)
            goto end;
        if (pkt->stream_index != audio_idx) {
            av_packet_unref(pkt);
            continue;
        }
        rc = avcodec_send_packet(dec_ctx, pkt);
        av_packet_unref(pkt);
        if (rc < 0)
            goto end;
        for (;;) {
            rc = avcodec_receive_frame(dec_ctx, dec_frame);
            if (rc == AVERROR(EAGAIN) || rc == AVERROR_EOF)
                break;
            if (rc < 0)
                goto end;
            rc = resample_frame(swr, enc_ctx, dec_frame, fifo);
            av_frame_unref(dec_frame);
            if (rc < 0)
                goto end;
            rc = encode_fifo(fifo, enc_ctx, ofmt, stream_idx, &next_pts, 0);
            if (rc < 0)
                goto end;
        }
    }
    avcodec_send_packet(dec_ctx, NULL);
    for (;;) {
        rc = avcodec_receive_frame(dec_ctx, dec_frame);
        if (rc == AVERROR_EOF)
            break;
        if (rc == AVERROR(EAGAIN))
            continue;
        if (rc < 0)
            goto end;
        rc = resample_frame(swr, enc_ctx, dec_frame, fifo);
        av_frame_unref(dec_frame);
        if (rc < 0)
            goto end;
        rc = encode_fifo(fifo, enc_ctx, ofmt, stream_idx, &next_pts, 0);
        if (rc < 0)
            goto end;
    }
    /* 잔여 리샘플러 지연 + fifo 잔량을 밀어낸 뒤, 마지막 짧은 조각까지 인코딩한다. */
    for (;;) {
        rc = resample_frame(swr, enc_ctx, NULL, fifo);
        if (rc < 0)
            goto end;
        rc = encode_fifo(fifo, enc_ctx, ofmt, stream_idx, &next_pts, 0);
        if (rc < 0)
            goto end;
        if (av_audio_fifo_size(fifo) == 0)
            break;
        /* swr delay 가 비어야 하는데 fifo 가 안 비면 무한루프 방지용 탈출 */
        break;
    }
    rc = encode_fifo(fifo, enc_ctx, ofmt, stream_idx, &next_pts, 1);
    if (rc < 0)
        goto end;
    rc = encode_frame(enc_ctx, NULL, ofmt, stream_idx);
    if (rc < 0)
        goto end;
    rc = av_write_trailer(ofmt);
    if (rc < 0)
        goto end;
    rc = 0;

end:
    av_packet_free(&pkt);
    av_frame_free(&dec_frame);
    av_audio_fifo_free(fifo);
    swr_free(&swr);
    avcodec_free_context(&dec_ctx);
    avcodec_free_context(&enc_ctx);
    if (ofmt) {
        if (!(ofmt->oformat->flags & AVFMT_NOFILE) && ofmt->pb)
            avio_closep(&ofmt->pb);
        avformat_free_context(ofmt);
    }
    avformat_close_input(&ifmt);
    return rc;
}
