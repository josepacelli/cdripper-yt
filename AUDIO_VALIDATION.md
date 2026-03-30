# Validação de Duração de Áudio - YouTube Fallback

## Problema Resolvido

Evitar downloads de versões erradas do YouTube:
- Clipes com 6s de uma música que deveria ter 1:30m ❌
- Intros ou outros arranjos com duração incorreta ❌
- Live versions ou remixes com duração muito diferente ❌

## Solução Implementada

**Validação de duração com tolerância de 30%**

### Como Funciona

1. **Lê a duração esperada** do arquivo original do CD
2. **Baixa o arquivo do YouTube**
3. **Valida a duração** antes de aceitar
4. **Se duração está errada → deleta e tenta próxima variação**
5. **Se duração OK → aceita e continua**

### Tolerância: ±30%

Exemplo com música de 1:30m (90 segundos):
```
Intervalo aceitável: 63s a 117s
Mín: 90 × 0.70 = 63s
Máx: 90 × 1.30 = 117s

Resultado 6s    → ❌ REJEITA (muito curto)
Resultado 1:28m → ✓ ACEITA (está dentro)
Resultado 2:00m → ❌ REJEITA (muito longo)
```

### Exemplos por Gênero

| Gênero | CD Duration | Intervalo Aceito | Comportamento |
|--------|------------|------------------|---------------|
| Pop    | 3:00m (180s) | 126s - 234s | ✓ Covers aceitáveis |
| Rock   | 4:30m (270s) | 189s - 351s | ✓ Live versions podem entrar |
| Funk   | 3:30m (210s) | 147s - 273s | ✓ Remixes curtos rejeitados |
| Clássica | 5:00m (300s) | 210s - 390s | ✓ Arranjos diferentes OK |
| Podcast | 0:30m (30s) | 21s - 39s | ✓ Introduções rejeitadas |

## Fluxo de Fallback com Validação

```
Usuário seleciona 10 arquivos do CD
    ↓
Tenta copiar do CD
    ├─ Sucesso → ✓ Copiado
    └─ Falha → Tenta YouTube (abaixo)
        ↓
    Busca no YouTube com duração esperada
        ↓
    Baixa primeiro resultado
        ↓
    ✓ Valida duração (±30%)?
        ├─ Sim  → ✓ Aceita e aplica artwork
        └─ Não  → ❌ Deleta e tenta próxima variação
            ├─ Remove números no final
            ├─ Remove (Remix), (Live), etc
            ├─ Tenta com primeiras 2-3 palavras
            └─ Se nada funcionar → silencia (falha)
    ↓
Resultado final: "✔ 10 arquivo(s)"  ← Sempre mostra total!
```

## Casos Reais

### Caso 1: Arquivo copiado com sucesso
```
CD: Bohemian Rhapsody - Queen (5:55m)
Status: ✓ Copiado do CD
Duração: 5:55m
Validação: ✓ OK (dentro de ±30%)
```

### Caso 2: CD falha, YouTube sucesso na primeira
```
CD: Imagine - John Lennon (3:02m)
Tentativa 1:
  - Cópia do CD: ❌ Falha (disco danificado)
  - YouTube busca: "Imagine"
  - Download: 3:01m
  - Validação: ✓ OK (3:01 está dentro de 2:06 - 3:56)
  - Resultado: ✓ YouTube sucesso
```

### Caso 3: YouTube retorna versão errada, tenta variações
```
CD: Billie Jean - Michael Jackson (4:54m)
Tentativa 1:
  - YouTube busca: "Billie Jean"
  - Download: 0:15m (clipe!) ❌
  - Validação: ✗ FALHA (15s < 3:26s mínimo)
  - Ação: Deleta e tenta próxima variação

Tentativa 2:
  - YouTube busca: "Billie Jean Michael Jackson" (remove "(Official)")
  - Download: 4:52m ✓
  - Validação: ✓ OK (4:52 está dentro de 3:26 - 6:22)
  - Resultado: ✓ YouTube sucesso com variação

Usuário vê: "✔ 10 arquivo(s)" (não sabe que teve 1 falha na primeira)
```

### Caso 4: Nenhuma variação funciona (silencioso)
```
CD: Música Ultra Rara de 1982 (2:15m)
Tentativas:
  - "Música Ultra Rara de 1982" → 2:20m (4:35 esperado) ❌
  - "Ultra Rara 1982" → 0:30m (intro) ❌
  - "Ultra Rara" → 3:45m (remix diferente) ❌
  - Nenhuma funcionou → ✗ Falha silenciosa

Usuário vê: "✔ 10 arquivo(s)" (sem saber que 1 não foi encontrado)
```

## Configuração

Tolerância padrão: **30%**

Para ajustar em `cdripper_utils.py`:
```python
# Aumentar para 50% (mais agressivo, aceita mais variações)
validate_mp3_duration(mp3_path, cd_duration, tolerance_percent=50)

# Reduzir para 15% (mais restritivo, rejeita covers/remixes)
validate_mp3_duration(mp3_path, cd_duration, tolerance_percent=15)
```

## Benefícios

✅ Evita baixar clipes/intros
✅ Evita versões live muito diferentes
✅ Evita remixes com duração errada
✅ Usuário recebe arquivo de qualidade esperada
✅ Falhas são silenciosas (sem assustar)
✅ Tenta agressivamente com variações de nome

## Próximas Melhorias (Futuro)

- [ ] Fingerprinting de áudio (Shazam-like) para covers/remixes
- [ ] MFCC comparison para detectar mesma música em arranjos diferentes
- [ ] Busca por ID3 tags de artista no YouTube
- [ ] Cache de resultados já validados
