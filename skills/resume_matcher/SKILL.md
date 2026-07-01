---
name: resume_matcher
description: Analyzes and matches a candidate's resume against a target Job Description to identify technical alignment, key competencies, and areas of weakness or gaps.
---

# Resume Matcher Skill

## Goal
To perform a detailed match between a candidate's resume and a target Job Description (JD) to identify key technical competencies, behavioral strengths, and developmental gaps.

## Instructions
1. **Analyze Input**:
   - Retrieve the candidate's resume text and the job description (JD) text from the session context or state.
2. **Compare Competencies**:
   - Compare the skills, experience levels, and responsibilities in the resume against those required in the JD.
   - Look for both direct matches and missing competencies.
3. **Identify Gaps**:
   - Identify up to 3 core technical gaps or areas of improvement (e.g., specific technologies, methodologies, or scale requirements).
   - Identify up to 2 behavioral gaps or areas of improvement (e.g., STAR structure, conflict resolution, metrics/impact framing).
4. **Generate Output**:
   - Provide a list of key competencies matched.
   - List the identified technical and behavioral gaps.
   - Suggest initial focus topics to test during the mock interview.

## Constraints
- Do not make assumptions about skills that are not explicitly or implicitly supported by the resume.
- Keep the evaluation professional and constructive.
