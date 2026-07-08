import os
import json
import re
import csv

# 1. 특수문자 및 기호 변환 매핑
LATEX_MAP = {
    '₀': '_0', '₁': '_1', '₂': '_2', '₃': '_3', '₄': '_4', '₅': '_5', '₆': '_6', '₇': '_7', '₈': '_8', '₉': '_9',
    '₊': '_{+}', '₋': '_{-}', '₌': '_{=}', '₍': '_{(}', '₎': '_{)}',
    '⁰': '^0', '¹': '^1', '²': '^2', '³': '^3', '⁴': '^4', '⁵': '^5', '⁶': '^6', '⁷': '^7', '⁸': '^8', '⁹': '^9',
    '⁺': '^{+}', '⁻': '^{-}', '⁼': '^{=}', '⁽': '^{(}', '⁾': '^{)}',
    '√': r'\sqrt', 
    'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta', 'ε': r'\epsilon', 'ζ': r'\zeta', 'η': r'\eta', 
    'θ': r'\theta', 'ι': r'\iota', 'κ': r'\kappa', 'λ': r'\lambda', 'μ': r'\mu', 'ν': r'\nu', 'ξ': r'\xi', 
    'π': r'\pi', 'ρ': r'\rho', 'σ': r'\sigma', 'τ': r'\tau', 'υ': r'\upsilon', 'φ': r'\phi', 'χ': r'\chi', 
    'ψ': r'\psi', 'ω': r'\omega',
    'Γ': r'\Gamma', 'Δ': r'\Delta', 'Θ': r'\Theta', 'Λ': r'\Lambda', 'Ξ': r'\Xi', 'Π': r'\Pi', 'Σ': r'\Sigma', 
    'Υ': r'\Upsilon', 'Φ': r'\Phi', 'Ψ': r'\Psi', 'Ω': r'\Omega',
    '±': r'\pm', '≤': r'\leq', '≥': r'\geq', '≠': r'\neq', '✕': r'\times', '×': r'\times', '÷': r'\div'
}

scientific_chars = "".join(LATEX_MAP.keys())
scientific_regex = re.compile(f'[{re.escape(scientific_chars)}]')
block_regex = re.compile(f'([a-zA-Z0-9\.\+\-\/]*[{re.escape(scientific_chars)}]+[a-zA-Z0-9\.\+\-\/]*)+')

def convert_symbols(text):
    if not text or not isinstance(text, str):
        return text
    if not scientific_regex.search(text):
        return text

    protections = []
    def protect(match):
        protections.append(match.group(0))
        return f"\x01{len(protections)-1}\x02"

    # Protection for footnotes or superscript parentheses (like `(67개)³)`)
    # Only protect superscripts if they are followed by a parenthesis/bracket/punctuation, 
    # OR preceded by non-math characters like Korean text or parentheses.
    text = re.sub(r"(?:[가-힣\)]\s*)[⁰¹²³⁴⁵⁶⁷⁸⁹]+[)\].,]*", protect, text)
    text = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]+[)\].,]+", protect, text)
    
    def replace_block(match):
        block = match.group(0)
        for k, v in LATEX_MAP.items():
            block = block.replace(k, v)
        # 만약 block이 완전히 placeholder로 이루어져 있다면 $ $로 감싸지 않음
        if re.fullmatch(r'(\x01\d+\x02)+', block):
            return block
        return f"${block}$"
        
    text = block_regex.sub(replace_block, text)

    for i, p in enumerate(protections):
        text = text.replace(f"\x01{i}\x02", p)
        
    return text

# 2. 분수 변환 (숫자, 문자, 한국어 특성 분수)
def convert_fractions(text):
    if not text or not isinstance(text, str):
        return text

    protections = []
    def protect(match):
        protections.append(match.group(0))
        return f"\x01{len(protections)-1}\x02"

    text = re.sub(r'https?://[^\s]+', protect, text)
    text = re.sub(r'팩/모듈사업', protect, text)
    text = re.sub(r'Index/Event', protect, text)

    text = re.sub(r'(?<![a-zA-Z0-9])(\d+)\s*/\s*(\d+)(?![a-zA-Z0-9])', r'$\\frac{\1}{\2}$', text)

    # 분수 형태의 단위 변환을 나중에 convert_variables에서 처리하기 위해 여기서는 protect로 보호
    text = re.sub(r'(?<![a-zA-Z])(?:km|m|mm|cm|kg|g|W|kW|MW)\s*/\s*(?:s|h|min|m|km|L)(?![a-zA-Z])', protect, text)

    def var_replacer(match):
        coeff = match.group(1) or ""
        num = match.group(2)
        den = match.group(3)
        return f"{coeff}$\\frac{{{num}}}{{{den}}}$"
        
    text = re.sub(r'(?<![a-zA-Z0-9])(\d+)?([a-zA-Z]{1,2})\s*/\s*([a-zA-Z]{1,2})(?![a-zA-Z0-9])', var_replacer, text)
    text = re.sub(r'\$([^\$]+)\$\s*/\s*\$([^\$]+)\$', r'$\\frac{\1}{\2}$', text)

    keywords = ['비율', '질량', '부피', '함량', '수', '밀도']
    stopwords = ['따라서', '은', '는', '이', '가', '을', '를', '다.', '한다.', 'ㄱ.', 'ㄴ.', 'ㄷ.', 'ㄹ.', '(단,', '그림', '표는', '그리고', '때,']
    
    parts = text.split('/')
    if len(parts) >= 2:
        for i in range(len(parts)-1):
            left = parts[i]
            right = parts[i+1]
            
            left_ends_with_kw = any(left.strip().endswith(kw) for kw in keywords)
            
            right_words = right.strip().split()
            right_match_idx = -1
            for j in range(min(4, len(right_words))):
                if any(right_words[j].endswith(kw) for kw in keywords):
                    right_match_idx = j
                    break
                    
            if left_ends_with_kw and right_match_idx != -1:
                left_words = left.split()
                num_words = []
                for w in reversed(left_words):
                    if w in stopwords or any(w.startswith(sw) and len(w) == len(sw) for sw in stopwords):
                        break
                    if w.endswith('.') or w.endswith(','):
                        num_words.append(w.rstrip('.,'))
                        break
                    num_words.append(w)
                num_words.reverse()
                numerator = " ".join(num_words)
                denominator = " ".join(right_words[:right_match_idx+1])
                
                escaped_num = re.escape(numerator)
                escaped_den = re.escape(denominator)
                pattern = re.compile(escaped_num + r'\s*/\s*' + escaped_den)
                text = pattern.sub(lambda m: f"$\\frac{{{numerator}}}{{{denominator}}}$", text, count=1)

    for i, p in enumerate(protections):
        text = text.replace(f"\x01{i}\x02", p)
        
    return text

# 3. 단일 알파벳 수학/물리 변수 변환
def convert_variables(text):
    if not text or not isinstance(text, str):
        return text

    protections = []
    def protect(match):
        protections.append(match.group(0))
        return f"\x01{len(protections)-1}\x02"

    text = re.sub(r'https?://[^\s]+', protect, text)
    text = re.sub(r'\$[^\$]+\$', protect, text) # 이미 변환된 수식 블록 보호
    
    # 예외 처리: HTML 태그에 의해 단어가 분리되어 단일 철자로 인식되는 현상 방지
    # 예: J<span>TBC</span>, 64<span>M</span> 등
    text = re.sub(r'[A-Za-z]+(?:<[^>]+>)+[A-Za-z]+', protect, text)
    text = re.sub(r'\d+(?:<[^>]+>)+[A-Za-z]+', protect, text)
    
    # 예외 처리: HTML 태그 자체 보호 (내부 p, a, b 등이 소문자 변수로 인식되는 것 방지)
    text = re.sub(r'<[^>]+>', protect, text)
    
    # 예외 처리: K R IL A 등 OCR 띄어쓰기 오류로 분리된 약어 보호
    # 대문자 1~2개가 공백으로 2번 이상 연결된 경우 중, 2글자짜리가 포함된 경우 보호
    def protect_spaced_abbr(match):
        s = match.group(0)
        if any(len(p) > 1 for p in s.split()):
            protections.append(s)
            return f"\x01{len(protections)-1}\x02"
        return s
    text = re.sub(r'\b[A-Za-z]{1,2}(?:\s+[A-Za-z]{1,2}){2,}\b', protect_spaced_abbr, text)
    
    # 예외 처리: 문맥상 확실한 비수학적 기호 및 로마자 보호
    text = re.sub(r'(?i)(?:제\s*\d+\s*호\s*)I\b', protect, text) # 제 00호 I
    text = re.sub(r'(?m)^I\.\s', protect, text) # I. 
    text = re.sub(r'\([CVEcve]\)', protect, text) # (C)opyright, (V)체크, (E)stimated
    text = re.sub(r'\b[QA]\.\d*', protect, text) # Q.31 등
    text = re.sub(r'<td>[QA]</td>', protect, text) # 테이블 내 단독 Q, A
    
    # [단위 변환 로직 추가]
    # 1. 온도 기호 변환 (정석 수식 형태 $^\circ C$ 로 치환)
    text = re.sub(r'℃|°C', r'$^\\circ C$', text)
    text = re.sub(r'°F', r'$^\\circ F$', text)

    # 2. 분수 형태의 단위 변환 (예: km/h -> $km/h$)
    text = re.sub(r'(?<![a-zA-Z])(?:km|m|mm|cm|kg|g|W|kW|MW)\s*/\s*(?:s|h|min|m|km|L)(?![a-zA-Z])', lambda m: f"${m.group(0)}$", text)

    # [새로운 보호 로직 추가: 단일 알파벳 예외 처리]
    # 1. 방향 기호 보호 (N, E, S, W)
    text = re.sub(r'\b[NESWnesw]\b', protect, text)
    
    # 2. 단순 점 좌표 보호 (예: A(a, b, -5), P(x, y))
    text = re.sub(r'\b[A-Z]\s*\([^)]+\)', protect, text)
    
    # 3. 인명 및 지칭 기호 보호 (예: A씨, B명, 대표 A, 학생 B)
    text = re.sub(r'(?<![A-Za-z0-9])[A-Z]\s*(?:씨|명|사람|군|양)(?![A-Za-z0-9])', protect, text)
    text = re.sub(r'(?:대표|학생|사람|점)\s+[A-Za-z](?![A-Za-z0-9])', protect, text)
    text = re.sub(r'(?<![A-Za-z0-9])[A-Z](?:\s*(?:와|과)\s*[A-Z])*\s*(?:두|세|네)?\s*(?:명|사람)(?![A-Za-z0-9])', protect, text)
    
    # 4. 보기 및 문항 기호 보호 (예: ①a, a:, b) )
    text = re.sub(r'[①-⑳]\s*[A-Za-z](?![A-Za-z0-9])', protect, text)
    text = re.sub(r'(?:^|\s)[a-zA-Z]\s*[:)]', protect, text)
    
    # 예외 처리: 통계에서 쓰이는 단순 표본 수 표기 (n=)
    text = re.sub(r'\bn\s*=', protect, text)
    
    # Protection for email
    text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', protect, text)
    
    # Protection for general abbreviation formats (like "K-IFRS", "R&D")
    text = re.sub(r'\b[A-Za-z]+(?:[-&][A-Za-z]+)+\b', protect, text)
    
    # Protection for Apostrophe (like "INTERNATIONAL'S")
    text = re.sub(r"[A-Za-z]+'[A-Za-z]+", protect, text)

    # 예외 처리: E(환경경영), S(사회책임) 등 한글 부가설명이 붙은 이니셜 보호 (태그 포함)
    text = re.sub(r'\b[A-Za-z](?:<[^>]+>)*\([가-힣]+\)', protect, text)
    
    # 예외 처리: 37°N, 131°E 등 방위 및 좌표 표시 보호
    text = re.sub(r'°[A-Za-z]\b', protect, text)
    
    # 예외 처리: 갤럭시 S 시리즈, 등 제품/시리즈 명칭 보호
    text = re.sub(r'갤럭시\s+[A-Za-z]\b', protect, text)
    text = re.sub(r'\b[A-Za-z](?:\s+|<[^>]+>)*시리즈\b', protect, text)
    
    # 예외 처리: p. 8, p. 25 등 페이지 표시 보호
    text = re.sub(r'(?i)\bp\.\s*\d+', protect, text)
    # 예외 처리: A형, B형 등 혈액형/유형 표시 보호
    text = re.sub(r'[A-Za-z]형\b', protect, text)
    
    # 3. 숫자 뒤에 붙은 알파벳 단위 변환 (예: 10m -> 10$m$, 100MHz -> 100$MHz$)
    # 예외적으로 3D, 5G 등은 위에서 보호되므로, 여기서는 남은 알파벳 단위들을 변환
    text = re.sub(r'(?<=\d)\s*([a-zA-Z]{1,3})(?![a-zA-Z0-9])', r'$\1$', text)
    
    pattern_upper = re.compile(r'(?<![a-zA-Z0-9\$])([A-Z])(?![a-zA-Z0-9\$])')
    text = pattern_upper.sub(r'$\1$', text)

    pattern_lower = re.compile(r'(?<![a-zA-Z0-9\$])([a-z])(?![a-zA-Z0-9\$])')
    text = pattern_lower.sub(r'$\1$', text)

    for i, p in enumerate(protections):
        text = text.replace(f"\x01{i}\x02", p)
        
    return text

# 메인 변환 파이프라인
def convert_all(text):
    text = convert_symbols(text)
    text = convert_fractions(text)
    text = convert_variables(text)
    return text

def main():
    src_dir = 'json'
    dst_dir = 'inline_latex'
    csv_report_path = 'conversion_report.csv'
    
    os.makedirs(dst_dir, exist_ok=True)
    
    files_processed = 0
    files_updated = 0
    changes_log = [] # CSV로 저장할 변경 내역 리스트
    
    for filename in os.listdir(src_dir):
        if not filename.endswith('.json'):
            continue
            
        file_path = os.path.join(src_dir, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            changed = False
            for det in data.get('layout_dets', []):
                for field in ['text', 'html']:
                    if field in det and isinstance(det[field], str):
                        original = det[field]
                        converted = convert_all(original)
                        if original != converted:
                            det[field] = converted
                            changed = True
                            
                            # html 필드의 경우 줄바꿈과 쉼표가 많아 CSV를 깨뜨릴 수 있으므로 정리
                            orig_clean = original.replace('\n', ' ').replace('\r', '')
                            conv_clean = converted.replace('\n', ' ').replace('\r', '')
                            
                            changes_log.append({
                                'Filename': filename,
                                'Field': field,
                                'Original': orig_clean,
                                'Converted': conv_clean
                            })
                            
            if changed:
                dst_path = os.path.join(dst_dir, filename)
                with open(dst_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                files_updated += 1
            files_processed += 1
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            
    # CSV 파일 저장
    with open(csv_report_path, 'w', encoding='utf-8-sig', newline='') as csvfile:
        fieldnames = ['Filename', 'Field', 'Original', 'Converted']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for row in changes_log:
            writer.writerow(row)
            
    print(f"==========================================")
    print(f"Total files scanned from '{src_dir}': {files_processed}")
    print(f"Files successfully converted and saved to '{dst_dir}': {files_updated}")
    print(f"Total text segments modified: {len(changes_log)}")
    print(f"Report saved to: {csv_report_path}")
    print(f"==========================================")

if __name__ == "__main__":
    main()
