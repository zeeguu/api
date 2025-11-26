# 0001. Multi-provider Text-to-Speech Architecture

**Status**: Accepted
**Date**: 2025-10-28
**Deciders**: Mircea, Claude

## Context

The Zeeguu audio lessons feature requires both male and female voices for dialog-based language learning. Users need to hear natural conversations between different speakers to learn pronunciation and context.

### Problems Identified

1. **Greek (el-GR)**: Google Cloud TTS only provides female voices (el-GR-Standard-B, el-GR-Wavenet-B)
2. **Romanian (ro-RO)**: Google Cloud TTS has no documented support for Romanian
3. **Single provider limitation**: Relying on a single TTS provider limits our language coverage

### Provider Research

| Provider | Greek Support | Romanian Support | Pricing |
|----------|--------------|------------------|---------|
| **Google Cloud TTS** | ✅ Female only | ❌ None | $4-16/million chars |
| **Azure Cognitive Services** | ✅ Male + Female | ✅ Male + Female | $15/million chars |
| **Amazon Polly** | ❌ None | ❌ None | N/A |

**Conclusion**: Azure is the only provider offering both male and female voices for Greek and Romanian.

## Decision

We will implement a **multi-provider TTS architecture** that:

1. **Routes by language**: Each language can specify its preferred TTS provider via configuration
2. **Maintains compatibility**: Existing Google TTS integration remains unchanged for other languages
3. **Adds Azure integration**: New Azure TTS wrapper for languages not well-supported by Google
4. **Transparent to callers**: The VoiceSynthesizer automatically routes to the correct provider

### Implementation

```python
# Voice configuration specifies provider
"el-GR": {
    "woman": "el-GR-AthinaNeural",
    "man": "el-GR-NestorasNeural",
    "provider": "azure"  # Routes to Azure
}

# Default behavior (no provider field) uses Google
"es-ES": {
    "woman": "es-ES-Chirp3-HD-Aoede",
    "man": "es-ES-Chirp3-HD-Algenib"
}
```

### Components Created

1. **AzureVoiceSynthesizer** - Azure TTS wrapper with compatible interface
2. **Provider routing logic** - Checks `provider` field in voice config
3. **Lazy initialization** - Azure client only created when needed
4. **Unified caching** - Works the same for both providers

## Consequences

### Positive

- ✅ **Unblocks Greek and Romanian**: Can now generate proper audio lessons with both genders
- ✅ **Future flexibility**: Easy to add more providers or switch languages between providers
- ✅ **Provider independence**: Not locked into a single vendor
- ✅ **Transparent migration**: Existing lessons/code unchanged
- ✅ **Best-of-breed**: Can choose the best voice quality per language

### Negative

- ❌ **Additional dependency**: azure-cognitiveservices-speech package (~30MB)
- ❌ **Configuration overhead**: Need to manage Azure credentials in addition to Google
- ❌ **Two billing relationships**: Invoices from both Google and Azure
- ❌ **Slightly more complexity**: More code paths and error handling

### Neutral

- ⚠️ **Caching remains effective**: Different voice IDs mean no cache conflicts
- ⚠️ **Similar pricing**: Azure and Google neural voices cost ~$15/million characters
- ⚠️ **API compatibility**: Both providers support SSML, rate control, and MP3 output

## Related

- **Implementation**: See `zeeguu/core/audio_lessons/azure_voice_synthesizer.py`
- **Configuration**: See `zeeguu/core/audio_lessons/voice_config.py`
- **Setup Guide**: See `docs/AZURE_TTS_SETUP.md`
- **Testing**: See `tools/test_azure_tts.py`

## Future Considerations

1. **Monitor usage**: Track costs per provider to optimize language assignments
2. **Voice quality**: Periodically review if Google adds missing voices
3. **More languages**: Consider Azure for other languages with limited Google support
4. **Fallback strategy**: Could implement automatic fallback if one provider fails
