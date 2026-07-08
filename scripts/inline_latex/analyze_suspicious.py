import csv
import re

# 수학/과학에서 매우 흔하게 쓰이는 변수들 (의심에서 제외)
math_vars = {
    '$x$', '$y$', '$z$', '$f$', '$g$', '$h$', '$t$', '$v$', '$n$', '$k$', '$i$', '$j$', 
    '$a$', '$b$', '$c$', '$d$', '$m$', '$p$', '$q$', '$r$', '$s$', '$w$',
    '$A$', '$B$', '$C$', '$D$', '$E$', '$F$', '$G$', '$H$', '$I$', '$J$', '$K$', '$L$', '$M$',
    '$N$', '$O$', '$P$', '$Q$', '$R$', '$S$', '$T$', '$U$', '$V$', '$W$', '$X$', '$Y$', '$Z$'
}

suspicious_cases = []

with open('conversion_report.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader) # skip header
    for row in reader:
        if len(row) < 4: continue
        filename, element_type, orig, conv = row
        
        matches = re.findall(r'\$[A-Za-z]{1,4}\$', conv)
        suspicious = [m for m in matches if m not in math_vars]
        
        # 만약 단일 대문자가 변환된 경우 중, "A는", "A가" 처럼 조사가 붙어있는 것도 의심해볼 수 있음
        # 하지만 앞서 A, B는 많이 제외했으므로, 이번엔 "A의", "A를" 도 찾아보자.
        single_upper_matches = re.findall(r'\$([A-Z])\$([가-힣]+)', conv)
        for var, josa in single_upper_matches:
            if josa.startswith(('의', '에', '에서', '가', '는', '은', '를', '을', '와', '과')):
                suspicious.append(f"${var}${josa}")
                
        # "점 $A$" 같은 것도 확인
        if "점 $" in conv:
            suspicious.append("점 $...$")
            
        if suspicious:
            suspicious_cases.append({
                'filename': filename,
                'orig': orig,
                'conv': conv,
                'suspicious': list(set(suspicious))
            })

with open('suspicious_report.md', 'w', encoding='utf-8') as f:
    f.write("# 🕵️ 추가 의심 변환 사례 분석 결과\n\n")
    f.write("수학/과학 변수로 흔히 쓰이지 않는 단어가 변환되었거나, 조사가 붙은 단일 대문자 변환 사례를 추출했습니다.\n\n")
    for idx, c in enumerate(suspicious_cases):
        f.write(f"### 사례 {idx+1}\n")
        f.write(f"- **의심 요소:** `{', '.join(c['suspicious'])}`\n")
        f.write(f"- **원본 (ORIG):** {c['orig']}\n")
        f.write(f"- **변환 (CONV):** {c['conv']}\n\n")
        
print(f"Total suspicious cases: {len(suspicious_cases)}")
