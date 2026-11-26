            const bool half_scale = (cmd.val & 0x200) && w >= 2 && h >= 2;
            const uint32_t copy_w = half_scale ? w / 2 : w;
            const uint32_t copy_h = half_scale ? h / 2 : h;
            GLuint tex = nwii::runtime::hle::TextureCache::get().find_efb_texture(dest);
            auto retained = s_retile_copies.find(dest & 0x01ffffffu);
            if (retained != s_retile_copies.end() &&
                copy_w == uint32_t(retained->second.baseWidth) &&
                copy_h == uint32_t(retained->second.baseHeight)) {
                tex = retained->second.base;
            }
            const bool had_copy = tex != 0;
            if (!tex) {
                glGenTextures(1, &tex);
            }
            glBindTexture(GL_TEXTURE_2D, tex);
            GLint existing_w = 0, existing_h = 0;
            if (had_copy) {
                glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH, &existing_w);
                glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT, &existing_h);
            }
            const uint32_t stride = g_state.efbCopyStride;
            const bool retile_rgba8 = had_copy && !half_scale &&
                ((cmd.val >> 3) & 15) == 12 && stride == copy_w * 16 &&
                existing_w > 0 && existing_h > 0 && existing_w % 4 == 0 &&
                existing_h % 4 == 0 && copy_w % 4 == 0 && copy_h % 4 == 0 &&
                copy_w > uint32_t(existing_w) &&
                (uint64_t(existing_w) * existing_h) % copy_w == 0 &&
                uint64_t(copy_h) < (uint64_t(existing_w) * existing_h) / copy_w;
            if (retile_rgba8) {
                tex = RetileRgba8Copy(dest, tex, existing_w, existing_h,
                    copy_w, copy_h, g_state.efbSrcX, g_state.efbSrcY, w, h);
                glBindTexture(GL_TEXTURE_2D, tex);
            } else {
                const bool partial_rgba8 = had_copy && ((cmd.val >> 3) & 15) == 12 &&
                    stride != 0 && stride % 16 == 0 &&
                    existing_w == GLint(stride / 16) &&
                    copy_w <= uint32_t(existing_w) && copy_h <= uint32_t(existing_h) &&
                    (copy_w < uint32_t(existing_w) || copy_h < uint32_t(existing_h));
                static GLuint copy_fbo = 0;
                if (!copy_fbo) {
                    glGenFramebuffers(1, &copy_fbo);
                }
                GLint previous_draw_fbo = 0;
                glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &previous_draw_fbo);
                if (!partial_rgba8) {
                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, copy_w, copy_h, 0,
                        GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
                }
                glBindFramebuffer(GL_DRAW_FRAMEBUFFER, copy_fbo);
                glFramebufferTexture2D(GL_DRAW_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                    GL_TEXTURE_2D, tex, 0);
                glDrawBuffer(GL_COLOR_ATTACHMENT0);
                glBlitFramebuffer(g_state.efbSrcX, 528 - int(g_state.efbSrcY),
                    g_state.efbSrcX + w, 528 - int(g_state.efbSrcY + h),
                    0, 0, copy_w, copy_h, GL_COLOR_BUFFER_BIT,
                    half_scale ? GL_LINEAR : GL_NEAREST);
                glBindFramebuffer(GL_DRAW_FRAMEBUFFER, GLuint(previous_draw_fbo));
            }
