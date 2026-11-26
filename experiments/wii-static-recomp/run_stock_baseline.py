"""Run owned stock diagnostics, or explicitly detached user play without a deadline."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import argparse
import re
import time
import tempfile
import sys
from collections import deque

parser = argparse.ArgumentParser()
run_length = parser.add_mutually_exclusive_group()
run_length.add_argument('--seconds', type=int, default=15)
run_length.add_argument('--until-closed', action='store_true')
parser.add_argument('--peek-address', type=lambda value: int(value, 16))
parser.add_argument('--peek-words', type=int, default=4)
parser.add_argument('--trace-calls', action='store_true')
parser.add_argument('--trace-only', default='')
parser.add_argument('--gx-trace', action='store_true')
parser.add_argument('--frame-trace', action='store_true')
parser.add_argument('--windowed', action='store_true')
parser.add_argument('--experimental-executable', type=Path)
parser.add_argument('--scheduler-observe', action='store_true')
parser.add_argument('--movie-timing', action='store_true')
parser.add_argument('--vi-timer-profile', action='store_true')
parser.add_argument('--pe-cadence-after-ms', type=int)
parser.add_argument('--cpu-sample-after-seconds', type=int)
parser.add_argument('--texture-observe', action='store_true')
parser.add_argument('--texture-capture-after-ms', type=int)
parser.add_argument('--texture-coherence', action='store_true')
parser.add_argument('--movie-capture-after-ms', type=int)
parser.add_argument('--thp-dump', action='store_true')
parser.add_argument('--thp-snapshot', action='store_true')
parser.add_argument('--capture', action='store_true')
parser.add_argument('--temporary-capture', action='store_true')
parser.add_argument('--temporary-evidence', action='store_true')
parser.add_argument('--test-ab-at-ms', type=int)
parser.add_argument('--test-select-at-ms', type=int)
parser.add_argument('--debug-overlay', action='store_true')
parser.add_argument('--dsp-supply', action='store_true')
parser.add_argument('--wall-tb', action='store_true')
parser.add_argument('--skip-wii-notices', action='store_true')
parser.add_argument('--tag', default='')
parser.add_argument('--loop-address', type=lambda value: int(value, 16))
parser.add_argument('--loop-chain', action='store_true')
parser.add_argument('--watch-address', type=lambda value: int(value, 16))
parser.add_argument('--loop-root', type=lambda value: int(value, 16))
parser.add_argument('--variant', choices=('stock', 'ipc-ack', 'ipc-queue', 'ipc-audio', 'ipc-natural', 'ipc-glguard', 'ipc-gldiag', 'ipc-cpbp', 'window-trace', 'window-warm', 'window-present', 'window-paced', 'window-hot-o2', 'window-lookup', 'window-psq', 'window-observe', 'window-byte-reverse', 'window-callback-observe', 'window-sound-observe', 'window-logical-record', 'window-ring-observe', 'window-optimized', 'window-cp-idle', 'window-cp-transport', 'window-transport-observe', 'window-transport-irq-order', 'window-completion-observe', 'window-draw-done', 'window-vi-path', 'window-hid2', 'window-hid2-carry', 'window-locked-cache', 'window-lc-numeric', 'window-lc-thp', 'window-quantization', 'window-idct-observe', 'window-psq-anomaly', 'window-thp-dcbz', 'window-fp-context', 'window-idct-fixtures', 'window-idct-callbacks', 'window-numeric-callbacks', 'window-numeric-unwind', 'window-fp-guard', 'window-wgp-stream', 'window-scan-restore', 'window-scan-routes', 'window-scan-observe', 'window-scan-consume', 'window-loading-observe', 'window-loading-payload', 'window-subtitle-progress', 'window-numeric-reader', 'window-numeric-flight', 'interpreter-carry-corrected', 'interpreter-addze-corrected', 'window-movie-queues', 'window-movie-update', 'window-movie-producer', 'window-movie-chain', 'window-movie-dma', 'window-sdk-enable-resume', 'window-context-observe', 'window-cache-observe', 'window-cache-filtered', 'window-legacy-context', 'window-input-sdk', 'window-fs-commands', 'window-nand-hierarchy', 'window-ipc-vector-observe', 'window-ipc-reply', 'window-texture-observe', 'window-buffer-flush-observe', 'window-fs-rename', 'window-tev-scope', 'headless-cache-irq', 'headless-sc-pc'), default='stock')
args = parser.parse_args()
if args.until_closed:
    assert args.windowed and args.temporary_evidence and args.variant == 'headless-sc-pc'
    assert args.experimental_executable is not None
    assert not any([args.trace_calls, args.gx_trace, args.frame_trace, args.scheduler_observe,
        args.movie_timing, args.vi_timer_profile, args.texture_observe, args.texture_coherence,
        args.thp_dump, args.thp_snapshot, args.capture, args.temporary_capture, args.loop_chain])
    assert args.trace_only == ''
    assert all(getattr(args, name) is None for name in ['peek_address', 'pe_cadence_after_ms',
        'cpu_sample_after_seconds', 'texture_capture_after_ms', 'movie_capture_after_ms',
        'test_ab_at_ms', 'test_select_at_ms', 'loop_address', 'watch_address', 'loop_root'])
assert 1 <= args.seconds <= 180
assert 1 <= args.peek_words <= 64
assert not args.capture or args.windowed
assert not args.temporary_capture or args.capture
assert not args.loop_chain or (args.loop_address is not None and args.variant == 'window-observe')
assert args.tag == '' or re.fullmatch(r'[a-z0-9-]{1,40}', args.tag)
project = Path('.').resolve()
root = project / 'work/private-game/static-recomp/stock-baseline'
game = project / 'work/private-game/disc/DATA'
exe = root / {'stock': 'export/build/OpenSHSMStockBaseline',
    'ipc-ack': 'ipc-ack/OpenSHSMStockIPCAck',
    'ipc-queue': 'ipc-queue/OpenSHSMStockIPCQueue',
    'ipc-audio': 'ipc-audio/OpenSHSMStockIPCAudio',
    'ipc-natural': 'ipc-natural/OpenSHSMStockIPCNatural',
    'ipc-gldiag': 'ipc-gldiag/OpenSHSMStockIPCGLDiag',
    'ipc-glguard': 'ipc-glguard/OpenSHSMStockIPCGLGuard',
    'ipc-cpbp': 'ipc-cpbp/OpenSHSMStockIPCCPBP',
    'window-trace': 'window-trace/OpenSHSMStockWindowTrace',
    'window-present': 'window-present/OpenSHSMStockWindowPresent',
    'window-paced': 'window-paced/OpenSHSMStockWindowPaced',
    'window-hot-o2': 'window-hot-o2/OpenSHSMStockHotO2',
    'window-lookup': 'window-lookup/OpenSHSMStockDispatchLookup',
    'window-psq': 'window-psq/OpenSHSMStockPSQIndexed',
    'window-observe': 'window-observe/OpenSHSMStockLoopObserver',
    'window-byte-reverse': 'window-byte-reverse/OpenSHSMStockByteReverse',
    'window-callback-observe': 'window-callback-observe/OpenSHSMStockCallbackObserver',
    'window-sound-observe': 'window-sound-observe/OpenSHSMStockSoundObserver',
    'window-logical-record': 'window-logical-record/OpenSHSMStockLogicalRecord',
    'window-ring-observe': 'window-ring-observe/OpenSHSMStockRingObserver',
    'window-optimized': 'window-optimized/OpenSHSMStockOptimized',
    'window-cp-idle': 'window-cp-idle/OpenSHSMStockCPIdle',
    'window-cp-transport': 'window-cp-transport/OpenSHSMStockCPTransport',
    'window-transport-observe': 'window-transport-observe/OpenSHSMStockTransportObserver',
    'window-transport-irq-order': 'window-transport-irq-order/OpenSHSMStockTransportIRQOrder',
    'window-completion-observe': 'window-completion-observe/OpenSHSMStockCompletionObserver',
    'window-draw-done': 'window-draw-done/OpenSHSMStockDrawDone',
    'window-hid2': 'window-hid2/OpenSHSMStockHID2',
    'window-hid2-carry': 'window-hid2-carry/OpenSHSMStockHID2Carry',
    'window-locked-cache': 'window-locked-cache/OpenSHSMStockLockedCache',
    'window-lc-numeric': 'window-lc-numeric/OpenSHSMStockNumericObserver',
    'window-lc-thp': 'window-lc-thp/OpenSHSMStockTHPObserver',
    'window-quantization': 'window-quantization/OpenSHSMStockQuantization',
    'window-idct-observe': 'window-idct-observe/OpenSHSMStockIDCTObserver',
    'window-thp-dcbz': 'window-thp-dcbz/OpenSHSMStockTHPDCBZ',
    'window-fp-context': 'window-fp-context/OpenSHSMStockFPContext',
    'window-psq-anomaly': 'window-psq-anomaly/OpenSHSMStockPSQAnomaly',
    'window-idct-fixtures': 'window-idct-fixtures/OpenSHSMStockIDCTFixtures',
    'window-idct-callbacks': 'window-idct-callbacks/OpenSHSMStockIDCTCallbacks',
    'window-numeric-callbacks': 'window-numeric-callbacks/OpenSHSMStockNumericCallbacks',
    'window-numeric-unwind': 'window-numeric-unwind/OpenSHSMStockNumericUnwind',
    'window-fp-guard': 'window-fp-guard/OpenSHSMStockFPGuard',
    'window-wgp-stream': 'window-wgp-stream/OpenSHSMStockWGPStream',
    'window-scan-restore': 'window-scan-restore/OpenSHSMStockScanRestore',
    'window-scan-routes': 'window-scan-routes/OpenSHSMStockScanRoutes',
    'window-scan-observe': 'window-scan-observe/OpenSHSMStockScanObserver',
    'window-scan-consume': 'window-scan-consume/OpenSHSMStockScanConsumer',
    'window-loading-observe': 'window-loading-observe/OpenSHSMStockLoadingObserver',
    'window-loading-payload': 'window-loading-payload/OpenSHSMStockLoadingPayload',
    'window-subtitle-progress': 'window-subtitle-progress/OpenSHSMStockSubtitleProgress',
    'window-numeric-reader': 'window-numeric-reader/OpenSHSMStockNumericReader',
    'window-numeric-flight': 'window-numeric-flight/OpenSHSMStockNumericFlight',
    'interpreter-carry-corrected': 'interpreter-carry-corrected/OpenSHSMStockInterpreterCarry',
    'interpreter-addze-corrected': 'interpreter-addze-corrected/OpenSHSMStockInterpreterAddze',
    'window-movie-queues': 'window-movie-queues/OpenSHSMStockMovieQueues',
    'window-movie-update': 'window-movie-update/OpenSHSMStockMovieUpdate',
    'window-movie-producer': 'window-movie-producer/OpenSHSMStockMovieProducer',
    'window-movie-chain': 'window-movie-chain/OpenSHSMStockMovieChain',
    'window-movie-dma': 'window-movie-dma/OpenSHSMStockMovieDMA',
    'window-sdk-enable-resume': 'window-sdk-enable-resume/OpenSHSMStockSDKEnableResume',
    'window-context-observe': 'window-context-observe/OpenSHSMStockContextObserver',
    'window-cache-observe': 'window-cache-observe/OpenSHSMStockCacheObserver',
    'window-cache-filtered': 'window-cache-filtered/OpenSHSMStockCacheFiltered',
    'window-legacy-context': 'window-legacy-context/OpenSHSMStockLegacyContext',
    'window-input-sdk': 'window-input-sdk/OpenSHSMStockInputSDK',
    'window-fs-commands': 'window-fs-commands/OpenSHSMStockFSCommands',
    'window-nand-hierarchy': 'window-nand-hierarchy/OpenSHSMStockNandHierarchy',
    'window-ipc-vector-observe': 'window-ipc-vector-observe/OpenSHSMStockIPCVectorObserve',
    'window-ipc-reply': 'window-ipc-reply/OpenSHSMStockIPCReply',
    'window-texture-observe': 'window-texture-observe/OpenSHSMStockTextureObserve',
    'window-buffer-flush-observe': 'window-buffer-flush-observe/OpenSHSMStockBufferFlushObserve',
    'window-fs-rename': 'window-fs-rename/OpenSHSMStockFSRename',
    'window-tev-scope': 'window-tev-scope/OpenSHSMStockTEVScope',
    'headless-cache-irq': 'headless-cache-irq-observe/OpenSHSMStockCacheIRQObserve',
    'headless-sc-pc': 'headless-sc-pc/OpenSHSMStockSCPC',
    'window-vi-path': 'window-vi-path/OpenSHSMStockVIPath',
    'window-warm': 'window-warm/OpenSHSMStockWindowWarm'}[args.variant]
cached_callback_profile = False
if args.experimental_executable is not None:
    exe = (root / args.experimental_executable).resolve()
    if not exe.is_relative_to(root):
        cache_options = {
            'OpenSHSMStockCallbackProfile': ('window-callback-profile', 'openshsm-callback-live-',
                'CALLBACK_PROFILE_ACTUAL_NONLOCAL4_FRAME_STATE_IDENTICAL3'),
            'OpenSHSMStockIOSO2': ('window-ios-o2', 'openshsm-ios-o2-',
                'IOS_O2_CALLBACK4_FRAME3_SDK7_SC3_PASS'),
            'OpenSHSMStockIOSO2Phases': ('window-ios-o2-phases', 'openshsm-ios-o2-phases-',
                'IOS_O2_EXISTING_OBSERVERS_SOURCE_LINK_VERIFIED'),
            'OpenSHSMStockTextureO2': ('window-texture-o2', 'openshsm-texture-o2-',
                'TEXTURE_O2_REAL_GL_PIXELS172_EVICTION1600_EQUAL'),
            'OpenSHSMStockMovieLate': ('window-movie-late', 'openshsm-movie-late-',
                'MOVIE_LATE_GATE_PACKET_FRAME_STATE_IDENTICAL3'),
            'OpenSHSMStockSchedulerO2': ('window-scheduler-o2', 'openshsm-scheduler-o2-',
                'SCHEDULER_O2_CONTRACT_CALLBACK4_SDK7_SC3_LATE18_EQUAL'),
            'OpenSHSMStockDispatchO2': ('window-dispatch-o2', 'openshsm-dispatch-o2-',
                'DISPATCH_O2_ROUTES_CALLBACK4_SDK7_SC3_LATE18_EQUAL'),
            'OpenSHSMStockCallbackO2Profile': ('window-callback-o2-profile', 'openshsm-callback-o2-',
                'CURRENT_CALLBACK_O2_PROFILE_NONLOCAL4_SDK7_SC3_LATE18_EQUAL'),
            'OpenSHSMStockCallbackWallProfile': ('window-callback-wall-profile', 'openshsm-callback-wall-',
                'CURRENT_CALLBACK_WALL_PROFILE_NONLOCAL4_SDK7_SC3_LATE18_EQUAL'),
            'OpenSHSMStockDECEEGate': ('window-dec-ee-gate', 'openshsm-dec-ee-gate-',
                'DEC_EE_GATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL'),
            'OpenSHSMStockCompletedFrame': ('window-completed-frame', 'openshsm-completed-frame-',
                'COMPLETED_FRAME_GL172_EVICTION1600_GPU16_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED'),
            'OpenSHSMStockPECadence': ('window-pe-cadence', 'openshsm-pe-cadence-',
                'PE_CADENCE_GPU16_SETTINGS3_RETAINED_PARENT_COMPONENTS_VERIFIED'),
            'OpenSHSMStockPostPresentDrain': ('window-post-present', 'openshsm-post-present-',
                'POST_PRESENT_GPU22_MAIN_DELTA_RETAINED_PARENT_COMPONENTS_VERIFIED'),
            'OpenSHSMStockSampleSymbols': ('window-sample-symbols', 'openshsm-sample-symbols-',
                'SAMPLE_SYMBOLS_SECTIONS_SIGNATURE_VERIFIED_FOR_PROFILING_ONLY'),
            'OpenSHSMStockContextStageGate': ('window-context-stage', 'openshsm-context-stage-gate-',
                'CONTEXT_STAGE_CACHE234_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED'),
            'OpenSHSMStockBPParseOrder': ('window-bp-order', 'openshsm-bp-parse-order-',
                'BP_ORDER_NATIVE_SHADER_GPU_PIPELINE_RETAINED_PARENT_VERIFIED'),
            'OpenSHSMStockPEExecute': ('window-pe-execute', 'openshsm-pe-execute-',
                'PE_EXECUTE_GL172_EVICTION1600_GPU6_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_VERIFIED'),
            'OpenSHSMStockTextureLate': ('window-texture-late', 'openshsm-texture-late-link-',
                'TEXTURE_LATE_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL'),
            'OpenSHSMStockDispatchSelect': ('window-dispatch-select', 'openshsm-dispatch-select-link-',
                'DISPATCH_SELECT_DEC9_CALLBACK4_SDK7_SC3_LATE18_TIMER3_EQUAL'),
            'OpenSHSMStockVIBusyLatch': ('window-vi-busy-latch', 'openshsm-vi-busy-latch-',
                'VI_BUSY_LATCH_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL'),
            'OpenSHSMStockVITimerProfile': ('window-vi-timer-profile', 'openshsm-vi-profile-link-',
                'VI_TIMER_PROFILE_DEC9_CALLBACK4_SDK7_SC3_LATE18_EQUAL'),
            'OpenSHSMStockCurrentVITimer': ('window-current-vi-timer', 'openshsm-current-vi-',
                'CURRENT_TIMER_MAIN_ONLY_LINK_SOURCE_SDK_MARKERS_VERIFIED')
        }
        assert exe.name in cache_options
        cache_directory, cache_prefix, cache_result = cache_options[exe.name]
        cache_build_path = root / cache_directory / 'build.json'
        cache_build = json.loads(cache_build_path.read_text())
        cache_component = json.loads((root / cache_directory / 'component-verification.json').read_text())
        assert exe == Path(cache_build['executablePath']).resolve()
        assert exe.parent.parent == Path('/private/tmp')
        assert re.fullmatch(re.escape(cache_prefix) + r'[A-Za-z0-9_-]+', exe.parent.name)
        assert cache_component['result'] == cache_result
        assert cache_component['buildSha256'] == hashlib.sha256(cache_build_path.read_bytes()).hexdigest()
        assert hashlib.sha256(exe.read_bytes()).hexdigest() == cache_build['executableSha256']
        cached_callback_profile = True
    assert (exe.is_relative_to(root) or cached_callback_profile) and exe.name in ('OpenSHSMStockTEVBanks', 'OpenSHSMStockObserverEnvCache', 'OpenSHSMStockSchedulerObserve', 'OpenSHSMStockMovieTiming', 'OpenSHSMStockConstantFP', 'OpenSHSMStockTHPSnapshot', 'OpenSHSMStockPSQScale', 'OpenSHSMStockTextureUnits', 'OpenSHSMStockTextureEviction', 'OpenSHSMStockTestAB', 'OpenSHSMStockTestProfile', 'OpenSHSMStockDebugOverlay', 'OpenSHSMStockDSPSupply', 'OpenSHSMStockADMAChunks', 'OpenSHSMStockADMAAccounting', 'OpenSHSMStockADMADeadline', 'OpenSHSMStockAudioRefill', 'OpenSHSMStockPCBoot', 'OpenSHSMStockAudioCallback', 'OpenSHSMStockDecoderO3', 'OpenSHSMStockLivePhases', 'OpenSHSMStockVITimer', 'OpenSHSMStockCPUTime', 'OpenSHSMStockDispatchCounts', 'OpenSHSMStockBoundsLookup', 'OpenSHSMStockMovieInput', 'OpenSHSMStockCallbackProfile', 'OpenSHSMStockIOSO2', 'OpenSHSMStockIOSO2Phases', 'OpenSHSMStockTextureO2', 'OpenSHSMStockMovieLate', 'OpenSHSMStockSchedulerO2', 'OpenSHSMStockDispatchO2', 'OpenSHSMStockCallbackO2Profile', 'OpenSHSMStockCallbackWallProfile', 'OpenSHSMStockDECEEGate', 'OpenSHSMStockCurrentVITimer', 'OpenSHSMStockVITimerProfile', 'OpenSHSMStockVIBusyLatch', 'OpenSHSMStockDispatchSelect', 'OpenSHSMStockTextureLate', 'OpenSHSMStockPEExecute', 'OpenSHSMStockCompletedFrame', 'OpenSHSMStockPECadence', 'OpenSHSMStockPostPresentDrain', 'OpenSHSMStockSampleSymbols', 'OpenSHSMStockContextStageGate', 'OpenSHSMStockBPParseOrder')
assert not args.debug_overlay or (args.windowed and exe.name in ('OpenSHSMStockDebugOverlay', 'OpenSHSMStockDSPSupply', 'OpenSHSMStockADMAChunks', 'OpenSHSMStockADMAAccounting', 'OpenSHSMStockADMADeadline', 'OpenSHSMStockAudioRefill', 'OpenSHSMStockPCBoot', 'OpenSHSMStockAudioCallback', 'OpenSHSMStockDecoderO3', 'OpenSHSMStockLivePhases', 'OpenSHSMStockVITimer', 'OpenSHSMStockCPUTime', 'OpenSHSMStockDispatchCounts', 'OpenSHSMStockBoundsLookup', 'OpenSHSMStockMovieInput', 'OpenSHSMStockCallbackProfile', 'OpenSHSMStockIOSO2', 'OpenSHSMStockIOSO2Phases', 'OpenSHSMStockTextureO2', 'OpenSHSMStockMovieLate', 'OpenSHSMStockSchedulerO2', 'OpenSHSMStockDispatchO2', 'OpenSHSMStockCallbackO2Profile', 'OpenSHSMStockCallbackWallProfile', 'OpenSHSMStockDECEEGate', 'OpenSHSMStockCurrentVITimer', 'OpenSHSMStockVITimerProfile', 'OpenSHSMStockVIBusyLatch', 'OpenSHSMStockDispatchSelect', 'OpenSHSMStockTextureLate', 'OpenSHSMStockPEExecute', 'OpenSHSMStockCompletedFrame', 'OpenSHSMStockPECadence', 'OpenSHSMStockPostPresentDrain', 'OpenSHSMStockSampleSymbols', 'OpenSHSMStockContextStageGate', 'OpenSHSMStockBPParseOrder'))
assert not args.dsp_supply or (args.windowed and exe.name in ('OpenSHSMStockDSPSupply', 'OpenSHSMStockADMAChunks', 'OpenSHSMStockADMAAccounting', 'OpenSHSMStockADMADeadline', 'OpenSHSMStockAudioRefill', 'OpenSHSMStockPCBoot', 'OpenSHSMStockAudioCallback', 'OpenSHSMStockDecoderO3', 'OpenSHSMStockLivePhases', 'OpenSHSMStockVITimer', 'OpenSHSMStockCPUTime', 'OpenSHSMStockDispatchCounts', 'OpenSHSMStockBoundsLookup', 'OpenSHSMStockMovieInput', 'OpenSHSMStockCallbackProfile', 'OpenSHSMStockIOSO2', 'OpenSHSMStockIOSO2Phases', 'OpenSHSMStockTextureO2', 'OpenSHSMStockMovieLate', 'OpenSHSMStockSchedulerO2', 'OpenSHSMStockDispatchO2', 'OpenSHSMStockCallbackO2Profile', 'OpenSHSMStockCallbackWallProfile', 'OpenSHSMStockDECEEGate', 'OpenSHSMStockCurrentVITimer', 'OpenSHSMStockVITimerProfile', 'OpenSHSMStockVIBusyLatch', 'OpenSHSMStockDispatchSelect', 'OpenSHSMStockTextureLate', 'OpenSHSMStockPEExecute', 'OpenSHSMStockCompletedFrame', 'OpenSHSMStockPECadence', 'OpenSHSMStockPostPresentDrain', 'OpenSHSMStockSampleSymbols', 'OpenSHSMStockContextStageGate', 'OpenSHSMStockBPParseOrder'))
assert not args.wall_tb or (args.windowed and (args.dsp_supply or args.until_closed) and exe.name in ('OpenSHSMStockADMAAccounting', 'OpenSHSMStockADMADeadline', 'OpenSHSMStockAudioRefill', 'OpenSHSMStockPCBoot', 'OpenSHSMStockAudioCallback', 'OpenSHSMStockDecoderO3', 'OpenSHSMStockLivePhases', 'OpenSHSMStockVITimer', 'OpenSHSMStockCPUTime', 'OpenSHSMStockDispatchCounts', 'OpenSHSMStockBoundsLookup', 'OpenSHSMStockMovieInput', 'OpenSHSMStockCallbackProfile', 'OpenSHSMStockIOSO2', 'OpenSHSMStockIOSO2Phases', 'OpenSHSMStockTextureO2', 'OpenSHSMStockMovieLate', 'OpenSHSMStockSchedulerO2', 'OpenSHSMStockDispatchO2', 'OpenSHSMStockCallbackO2Profile', 'OpenSHSMStockCallbackWallProfile', 'OpenSHSMStockDECEEGate', 'OpenSHSMStockCurrentVITimer', 'OpenSHSMStockVITimerProfile', 'OpenSHSMStockVIBusyLatch', 'OpenSHSMStockDispatchSelect', 'OpenSHSMStockTextureLate', 'OpenSHSMStockPEExecute', 'OpenSHSMStockCompletedFrame', 'OpenSHSMStockPECadence', 'OpenSHSMStockPostPresentDrain', 'OpenSHSMStockSampleSymbols', 'OpenSHSMStockContextStageGate', 'OpenSHSMStockBPParseOrder'))
assert not args.skip_wii_notices or (args.windowed and exe.name in ('OpenSHSMStockPCBoot', 'OpenSHSMStockAudioCallback', 'OpenSHSMStockDecoderO3', 'OpenSHSMStockLivePhases', 'OpenSHSMStockVITimer', 'OpenSHSMStockCPUTime', 'OpenSHSMStockDispatchCounts', 'OpenSHSMStockBoundsLookup', 'OpenSHSMStockMovieInput', 'OpenSHSMStockCallbackProfile', 'OpenSHSMStockIOSO2', 'OpenSHSMStockIOSO2Phases', 'OpenSHSMStockTextureO2', 'OpenSHSMStockMovieLate', 'OpenSHSMStockSchedulerO2', 'OpenSHSMStockDispatchO2', 'OpenSHSMStockCallbackO2Profile', 'OpenSHSMStockCallbackWallProfile', 'OpenSHSMStockDECEEGate', 'OpenSHSMStockCurrentVITimer', 'OpenSHSMStockVITimerProfile', 'OpenSHSMStockVIBusyLatch', 'OpenSHSMStockDispatchSelect', 'OpenSHSMStockTextureLate', 'OpenSHSMStockPEExecute', 'OpenSHSMStockCompletedFrame', 'OpenSHSMStockPECadence', 'OpenSHSMStockPostPresentDrain', 'OpenSHSMStockSampleSymbols', 'OpenSHSMStockContextStageGate', 'OpenSHSMStockBPParseOrder'))
if args.test_ab_at_ms is not None:
    assert exe.name in ('OpenSHSMStockTestAB', 'OpenSHSMStockTestProfile') and 0 <= args.test_ab_at_ms < args.seconds * 1000 - 1000
if args.movie_capture_after_ms is not None:
    assert args.movie_timing and exe.name in ('OpenSHSMStockMovieLate', 'OpenSHSMStockSchedulerO2', 'OpenSHSMStockDispatchO2', 'OpenSHSMStockCallbackO2Profile', 'OpenSHSMStockCallbackWallProfile', 'OpenSHSMStockDECEEGate', 'OpenSHSMStockCurrentVITimer', 'OpenSHSMStockVITimerProfile', 'OpenSHSMStockVIBusyLatch', 'OpenSHSMStockDispatchSelect', 'OpenSHSMStockTextureLate', 'OpenSHSMStockPEExecute', 'OpenSHSMStockCompletedFrame', 'OpenSHSMStockPECadence', 'OpenSHSMStockPostPresentDrain', 'OpenSHSMStockSampleSymbols', 'OpenSHSMStockContextStageGate', 'OpenSHSMStockBPParseOrder')
    assert 0 <= args.movie_capture_after_ms <= 180000
    assert args.movie_capture_after_ms < args.seconds * 1000
if args.pe_cadence_after_ms is not None:
    assert args.windowed and exe.name in ('OpenSHSMStockPECadence', 'OpenSHSMStockPostPresentDrain')
    assert 0 <= args.pe_cadence_after_ms <= 180000 and args.pe_cadence_after_ms < args.seconds * 1000
if args.cpu_sample_after_seconds is not None:
    assert sys.platform == 'darwin'
    assert args.windowed and args.temporary_evidence and args.tag == 'post-present-profile'
    assert exe.name in ('OpenSHSMStockPostPresentDrain', 'OpenSHSMStockSampleSymbols')
    assert 0 <= args.cpu_sample_after_seconds <= args.seconds - 15
if args.test_select_at_ms is not None:
    assert exe.name == 'OpenSHSMStockTestProfile' and args.test_ab_at_ms is not None
    assert args.test_ab_at_ms + 1750 <= args.test_select_at_ms < args.seconds * 1000 - 1000
assert exe.name != 'OpenSHSMStockTestProfile' or ((args.test_ab_at_ms is None) == (args.test_select_at_ms is None))
def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
original_hash = sha(game / 'sys/main.dol')
assert not args.texture_observe or (args.windowed and exe.name in ('OpenSHSMStockTextureLate', 'OpenSHSMStockPEExecute', 'OpenSHSMStockCompletedFrame', 'OpenSHSMStockPECadence', 'OpenSHSMStockPostPresentDrain', 'OpenSHSMStockSampleSymbols', 'OpenSHSMStockContextStageGate', 'OpenSHSMStockBPParseOrder'))
assert not args.texture_coherence or args.texture_observe
if args.texture_capture_after_ms is not None:
    assert args.texture_observe and 0 <= args.texture_capture_after_ms <= 180000
    assert args.texture_capture_after_ms < args.seconds * 1000
assert not args.vi_timer_profile or (args.windowed and exe.name == 'OpenSHSMStockVITimerProfile')
assert original_hash == 'ef1a39ea96367ddc0c0070923c247c9bbe56c7c64045795a13430e1e9b00ae6f'
assert exe.exists()
if args.until_closed:
    assert exe.name == 'OpenSHSMStockBPParseOrder'
work = root / 'user'
work.mkdir(exist_ok=True)
config = work / 'config.toml'
if not args.until_closed or not config.exists():
    config.write_text('[system]\nplatform = "Wii"\n[game]\nid = "R5WEA4"\n[input]\nmode = 6\n[graphics]\nbackend = "OpenGL"\nwindow_width = 960\nwindow_height = 540\n')
env = {key: value for key, value in os.environ.items() if not key.startswith(('SHSM_', 'NWII_'))}
env.update(NWII_HEADLESS='0' if args.windowed else '1', NWII_SAMPLE='1')
if args.pe_cadence_after_ms is not None:
    env['NWII_PE_CADENCE_AFTER_MS'] = str(args.pe_cadence_after_ms)
if args.vi_timer_profile:
    env['NWII_VI_TIMER_PROFILE'] = '1'
if args.debug_overlay:
    env['NWII_DEBUG_OVERLAY'] = '1'
if args.dsp_supply:
    env['NWII_DSP_SUPPLY'] = '1'
if args.wall_tb:
    env['NWII_WALLTB'] = '1'
if args.skip_wii_notices:
    env['NWII_SKIP_BOOT_NOTICES'] = '1'
if args.test_ab_at_ms is not None:
    env['NWII_TEST_AB_AT_MS'] = str(args.test_ab_at_ms)
if args.test_select_at_ms is not None:
    env['NWII_TEST_SELECT_AT_MS'] = str(args.test_select_at_ms)
artifact_root = Path(tempfile.mkdtemp(prefix='openshsm-run-', dir='/private/tmp')) if args.temporary_evidence else root
print('Owned diagnostic artifacts', artifact_root, flush=True)
artifact_label = args.variant + ('-' + args.tag if args.tag else '')
if args.thp_snapshot:
    assert args.thp_dump
    snapshot_path = artifact_root / (artifact_label + '-decoder-entry.bin')
    assert not snapshot_path.exists(), 'Refuse to overwrite decoder snapshot'
    env['NWII_THP_SNAPSHOT'] = str(snapshot_path)
if args.thp_dump:
    assert {'80209d80', '80217d30'} <= set(args.trace_only.lower().split(','))
    thp_prefix = artifact_root / (artifact_label + '-thp')
    assert not list(artifact_root.glob(thp_prefix.name + '-*')), 'Refuse to overwrite existing THP evidence'
    env['NWII_THPDUMP'] = str(thp_prefix)
if args.movie_timing:
    timing_path = artifact_root / (artifact_label + '-movie-timing.jsonl')
    assert not timing_path.exists()
    env['NWII_MOVIE_TIMING'] = str(timing_path)
if args.movie_capture_after_ms is not None:
    env['NWII_MOVIE_CAPTURE_AFTER_MS'] = str(args.movie_capture_after_ms)
if args.scheduler_observe:
    scheduler_prefix = artifact_root / (artifact_label + '-sched')
    assert not Path(str(scheduler_prefix) + '-scheduler.jsonl').exists()
    env['NWII_SCHED_OBSERVE'] = str(scheduler_prefix)
if args.variant == 'window-tev-scope':
    env['NWII_SHADERPROFILE'] = '1'
texture_output = None
if args.variant == 'window-texture-observe' or args.texture_observe:
    texture_output = artifact_root / (artifact_label + '-textures')
    texture_output.mkdir(exist_ok=False)
    env['NWII_TEXTURE_OBSERVE'] = str(texture_output)
if args.texture_capture_after_ms is not None:
    env['NWII_TEXTURE_CAPTURE_AFTER_MS'] = str(args.texture_capture_after_ms)
if args.texture_coherence:
    env['NWII_TEXTURE_COHERENCE'] = '1'
if args.variant == 'window-wgp-stream':
    env['NWII_GXDUMP'] = str(artifact_root / (artifact_label + '-gx-stream.bin'))
    env['NWII_WGSEG'] = str(artifact_root / (artifact_label + '-gx-segments.txt'))
    env['NWII_WGBURSTS'] = str(artifact_root / (artifact_label + '-gx-bursts.bin'))
    env['NWII_CPSTREAM'] = str(artifact_root / (artifact_label + '-gx-cp.bin'))
if args.variant in ('window-lc-thp', 'window-quantization', 'window-idct-observe', 'window-thp-dcbz', 'window-fp-context', 'window-psq-anomaly', 'window-idct-fixtures', 'window-idct-callbacks', 'window-numeric-callbacks', 'window-numeric-unwind', 'window-fp-guard', 'window-scan-restore', 'window-scan-routes', 'window-scan-observe', 'window-scan-consume', 'window-loading-observe', 'window-loading-payload', 'window-subtitle-progress', 'window-numeric-reader', 'window-numeric-flight', 'interpreter-carry-corrected', 'interpreter-addze-corrected', 'window-movie-queues', 'window-movie-update', 'window-movie-producer', 'window-movie-chain', 'window-movie-dma', 'window-sdk-enable-resume', 'window-context-observe', 'window-cache-observe', 'window-cache-filtered', 'window-legacy-context'):
    env['NWII_THPDUMP'] = str(artifact_root / (artifact_label + '-thp'))
if args.trace_calls:
    env['NWII_TRACE_CALLS'] = '1'
if args.trace_only:
    assert re.fullmatch(r'[0-9a-fA-F]{8}(,[0-9a-fA-F]{8}){0,15}', args.trace_only)
    assert all(0x80004000 <= int(value, 16) < 0x81800000 for value in args.trace_only.split(','))
    env['NWII_TRACE_CALLS'] = '1'
    env['NWII_TRACE_ONLY'] = args.trace_only
if args.gx_trace:
    env.update(NWII_CPTRACE='1', NWII_GXTRACE='1')
    env['NWII_GXDUMP'] = str(artifact_root / (artifact_label + '-gx-stream.bin'))
    env['NWII_WGSEG'] = str(artifact_root / (artifact_label + '-gx-segments.txt'))
if args.frame_trace:
    env.update(NWII_VTXTRACE='1', NWII_TEVTRACE='1', NWII_SHADERDUMP='1', NWII_FRAMESIG='1')
capture_prefix = None
if args.capture:
    capture_root = Path(tempfile.mkdtemp(prefix='openshsm-captures-', dir='/private/tmp')) if args.temporary_capture else artifact_root
    capture_prefix = capture_root / (artifact_label + '-efb')
    assert not list(capture_root.glob(capture_prefix.name + '_*.bmp'))
    env['NWII_SCREENSHOT'] = str(capture_prefix)
if args.loop_address is not None:
    assert 0x80004000 <= args.loop_address < 0x81800000
    env['NWII_LOOPTRACE'] = f'{args.loop_address:x}'
if args.loop_chain:
    env['NWII_LOOPCHAIN'] = '1'
if args.loop_root is not None:
    assert args.loop_chain and (args.loop_root & 3) == 0
    assert 0x80004000 <= args.loop_root <= 0x817FFFFC or 0x90000000 <= args.loop_root <= 0x93FFFFFC
    env['NWII_LOOPROOT'] = f'{args.loop_root:x}'
if args.watch_address is not None:
    assert (args.watch_address & 3) == 0
    assert 0x80004000 <= args.watch_address <= 0x817FFFFC or 0x90000000 <= args.watch_address <= 0x93FFFFFC
    env['NWII_WATCH'] = f'{args.watch_address:x}'
    env['NWII_WATCH_REGS'] = '1'
if args.peek_address is not None:
    assert 0x80004000 <= args.peek_address <= 0x817fffe0 or 0x90000000 <= args.peek_address <= 0x93ffffe0
    assert (args.peek_address & 3) == 0
    assert (args.peek_address + args.peek_words * 4 <= 0x81800000 if args.peek_address < 0x90000000 else args.peek_address + args.peek_words * 4 <= 0x94000000)
    env['NWII_PEEK'] = f'{args.peek_address:x},{args.peek_words}'
label = 'stock-trace' if args.trace_calls or args.loop_address is not None else 'stock-peek' if args.peek_address is not None else 'stock-headless'
if args.variant != 'stock':
    label = label.replace('stock-', args.variant + '-')
if args.gx_trace:
    label += '-gx'
if args.windowed:
    label += '-windowed'
if args.frame_trace:
    label += '-frame'
if args.tag:
    label += '-' + args.tag
log = artifact_root / (label + '.log')
if args.until_closed:
    env.pop('NWII_SAMPLE', None)
    process = subprocess.Popen([str(exe), str(game), str(config)], cwd=work, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    print('Owned user-play runtime PID', process.pid, 'no automatic deadline', flush=True)
    time.sleep(1)
    returncode = process.poll()
    (artifact_root / (label + '-result.json')).write_text(json.dumps({
        'result': 'USER_PLAY_STARTED_WITHOUT_DEADLINE' if returncode is None else 'USER_PLAY_EARLY_EXIT',
        'pid': process.pid, 'terminalReturncode': returncode, 'deadlineReached': False, 'seconds': None,
        'executablePath': str(exe), 'executableSha256': sha(exe), 'configPath': str(config),
        'configSha256': sha(config), 'originalDolSha256': original_hash, 'recipeSha256': sha(Path(__file__)),
        'debugOverlay': args.debug_overlay, 'wallTimebase': args.wall_tb,
        'skipWiiNotices': args.skip_wii_notices, 'stdoutPolicy': 'discarded',
        'limits': ['Detached user-owned session, no timer/watchdog/log-size termination.',
            'Initial child-alive check only, not menu/gameplay/fidelity verification.']}, indent=2) + '\n')
    assert returncode is None, f'User-play executable exited during startup: {returncode}'
    sys.exit(0)
timed_out = False
log_limit_reached = False
cpu_sampler = None
cpu_sample_returncode = None
cpu_sample_log = artifact_root / 'cpu-sample-collector.log'
with log.open('w') as stream:
    process = subprocess.Popen([str(exe), str(game), str(config)], cwd=work, env=env,
        stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
    print('Owned stock runtime PID', process.pid, flush=True)
    deadline = time.monotonic() + args.seconds
    cpu_sample_at = deadline - args.seconds + args.cpu_sample_after_seconds if args.cpu_sample_after_seconds is not None else None
    while process.poll() is None:
        timed_out = time.monotonic() >= deadline
        log_limit_reached = log.stat().st_size >= 64 * 1024 * 1024
        if timed_out or log_limit_reached:
            break
        if cpu_sample_at is not None and cpu_sampler is None and time.monotonic() >= cpu_sample_at:
            with cpu_sample_log.open('w') as collector_stream:
                cpu_sampler = subprocess.Popen([sys.executable,
                    str(project / 'experiments/wii-static-recomp/sample_stock_owned_runtime.py'),
                    '--artifacts', str(artifact_root), '--pid', str(process.pid), '--executable', str(exe)],
                    stdout=collector_stream, stderr=subprocess.STDOUT)
            print('Owned CPU sample collector PID', cpu_sampler.pid, flush=True)
        try:
            process.wait(timeout=min(1, max(0.01, deadline - time.monotonic())))
        except subprocess.TimeoutExpired:
            pass
    if process.poll() is None:
        process.terminate()
        try:
            returncode = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait(timeout=5)
    else:
        returncode = process.returncode
if cpu_sampler is not None:
    try:
        cpu_sample_returncode = cpu_sampler.wait(timeout=10)
    except subprocess.TimeoutExpired:
        cpu_sampler.terminate()
        try:
            cpu_sample_returncode = cpu_sampler.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cpu_sampler.kill()
            cpu_sample_returncode = cpu_sampler.wait(timeout=5)
assert process.poll() is not None and sha(game / 'sys/main.dol') == original_hash
lines = deque(maxlen=20)
samples = deque(maxlen=30)
with log.open(errors='replace') as stream:
    for line in stream:
        line = line.rstrip('\n')
        lines.append(line)
        if '[Sample]' in line or '[Peek]' in line or 'CRASHED' in line or 'shutdown' in line:
            samples.append(line)
(artifact_root / (label + '-result.json')).write_text(json.dumps({'result': 'BOUNDED_STOCK_RUN_COMPLETE',
    'pid': process.pid, 'terminalReturncode': returncode, 'deadlineReached': timed_out, 'seconds': args.seconds,
    'cpuSampleAfterSeconds': args.cpu_sample_after_seconds, 'cpuSampleReturncode': cpu_sample_returncode,
    'cpuSampleLogSha256': sha(cpu_sample_log) if cpu_sampler is not None else None,
    'logLimitReached': log_limit_reached, 'logLimitBytes': 64 * 1024 * 1024,
    'executableSha256': sha(exe), 'configSha256': sha(config), 'logSha256': sha(log),
    'originalDolSha256': original_hash, 'recipeSha256': sha(Path(__file__)), 'samples': list(samples),
    'peekAddress': args.peek_address,
    'peekWords': args.peek_words, 'frameTrace': args.frame_trace,
    'traceCalls': args.trace_calls, 'loopAddress': args.loop_address,
    'traceOnly': args.trace_only,
    'loopChain': args.loop_chain,
    'watchAddress': args.watch_address,
    'loopRoot': args.loop_root,
    'variant': args.variant,
    'gxTrace': args.gx_trace,
    'windowed': args.windowed,
    'experimentalExecutable': str(args.experimental_executable) if args.experimental_executable else None,
    'schedulerObserve': args.scheduler_observe,
    'movieTiming': args.movie_timing,
    'viTimerProfile': args.vi_timer_profile,
    'textureObserve': args.texture_observe or args.variant == 'window-texture-observe',
    'textureCaptureAfterMs': args.texture_capture_after_ms,
    'textureCoherence': args.texture_coherence,
    'textureDirectory': str(texture_output) if texture_output else None,
    'movieCaptureAfterMs': args.movie_capture_after_ms,
    'peCadenceAfterMs': args.pe_cadence_after_ms,
    'thpDump': args.thp_dump,
    'thpSnapshot': args.thp_snapshot,
    'capture': args.capture,
    'artifactDirectory': str(artifact_root),
    'temporaryEvidence': args.temporary_evidence,
    'temporaryCapture': args.temporary_capture,
    'capturePrefix': str(capture_prefix) if capture_prefix else None,
    'testABAtMs': args.test_ab_at_ms,
    'testSelectAtMs': args.test_select_at_ms,
    'debugOverlay': args.debug_overlay,
    'dspSupply': args.dsp_supply,
    'wallTimebase': args.wall_tb,
    'skipWiiNotices': args.skip_wii_notices,
    'tag': args.tag,
    'limits': ['Runtime log alone is not original behavior oracle, rendered-image or first-screen proof.',
        'Upstream virtual NAND uses synthetic in-memory system files; no source NAND or prepared game file writes.']}, indent=2) + '\n')
print('Owned runtime terminal', returncode, 'deadline reached:', timed_out)
print('\n'.join(list(samples)[-12:] if samples else lines))
