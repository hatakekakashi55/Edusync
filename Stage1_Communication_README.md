# Edusync: Stage 1 - Communication Skills (Workflow & App Implementation Guide)

## Overview
This document contains the detailed workflow, features, and UI/UX structure of the **Stage 1: Communication Skills** module from the Edusync website. This guide serves as the foundation for implementing these exact features into the **EduSync Mobile App**.

---

## 1. Dashboard & Progress Tracking (Home)
**Structure:**
- **Metrics/Score Cards:** Displays Total Challenges Completed, Average Score, Vocabulary Words Learned, and Practice Hours.
- **Weekly Progress Graph/Chart:** Visual representation of user activity.
- **Quick Actions:** Easy access to add new words or resume the last lesson.

**App Workflow:**
- Landing page defaults to an overall summary.
- Users can see their streak and their progress toward weekly vocabulary or challenge goals.

---

## 2. Listening Comprehension Module
**Features & Workflows:**
1. **Echo Challenge:**
   - *Workflow:* User plays a predefined or AI-generated audio sentence -> User repeats the sentence using the microphone -> System evaluates and scores pronunciation accuracy.
2. **Fill the Beats:**
   - *Workflow:* Audio plays while a transcript with missing words is displayed -> User fills in the blanks based on what they hear -> Submits for score.
3. **Direction Follower:**
   - *Workflow:* User listens to an audio clip containing specific directions -> User traces the path on a visual grid/map -> Clicks "Check My Path" for validation.
4. **Tone Recognizer:**
   - *Workflow:* User plays a short voice clip -> Evaluates whether the tone is happy, angry, professional, etc., and selects the correct option.

---

## 3. Reading Mastery Module
**Features & Workflows:**
1. **Passage Reading & Comprehension:**
   - *Workflow:* User selects a reading source (Admin-curated / Faculty hand-picked OR dynamically AI-generated) -> Reads passage within a possible time limit -> Answers a series of multiple-choice or short-answer questions to test comprehension -> Gets evaluated.

---

## 4. Writing Excellence Module
**Features & Workflows:**
1. **Essay Challenges:**
   - *Workflow:* User receives a topic -> Writes an essay -> System provides real-time grammatical, structural, and vocabulary feedback.
2. **Picture Prompt (Visual Writing):**
   - *Workflow:* An image is shown on screen -> User observes and writes a creative 50-word description -> Submits for evaluation.
3. **No-Filter Challenge (Vocabulary Expansion):**
   - *Workflow:* A simple sentence is provided (e.g., "The food was very good") along with BANNED words (e.g., "very", "good") -> User must rewrite the exact paragraph using advanced vocabulary (e.g., "The cuisine was exceedingly delightful") without triggering banned words -> Submits.
4. **Quick Reply Time Attack:**
   - *Workflow:* User receives a mock email (e.g., from a manager needing a report) -> Timer starts -> User must draft a polite, professional reply -> Submits before the clock runs out -> Receives feedback on tone and grammar.
5. **Word Chain:**
   - *Workflow:* Form an exact 10-word meaningful sentence meeting certain criteria -> Evaluated for logic and vocabulary.

---

## 5. Speaking Fluency & AI Conversational Tools
**Features & Workflows:**
1. **AI Conversation Partner:**
   - *Workflow:* Clicking the microphone initiates a continuous real-time voice or chat session with the AI -> The AI simulates a real-life conversation partner -> Provides instant feedback on mistakes.
2. **English Learning AI Chatbot (Ollama Powered):**
   - *Workflow:* Dedicated Chat window with 4 distinct mode tabs:
     - **General:** All-in-one learning support.
     - **Conversation:** Free-flowing text conversation practice.
     - **Grammar:** Paste sentences to instantly correct and improve writing.
     - **Pronunciation:** Guidance on mastering specific English phonetic sounds.

---

## 6. Vocabulary Builder (Flashcards System)
**Features & Workflows:**
- **Daily Word Cards:** Users swipe or flip flashcards displaying: English Word, English Meaning, Tamil Meaning, Example Sentence, Category (e.g., Business, Academic, Basic).
- **Add New Word Form:** Users can actively type and add their own words into the app's database. Requires: Word, Meaning, Tamil Meaning, Examples, Notes.
- **Vocabulary Progress View:** Badges, tracked streaks, and a downloadable report of mastered words.

---

## App Implementation Notes (for Mobile Developer)
- **UI/UX Strategy:** Use clean, rounded cards (`feature-card`, `selection-card`) and clear distinct tabs mimicking the website's dark/light modern themes and glassmorphism aspects.
- **Audio/Mic Permissions:** The mobile app must request microphone access natively for the Echo Challenge, Tone Recognizer, and the AI Conversation partner. Be sure to handle Android and iOS permission prompt flows effectively.
- **Gamification Elements:** Be sure to build out the UI to show credit costs (e.g., "10 Credits", "20 Credits") and difficulty levels (Medium, Hard) as badges on challenge selectors.
- **AI Backend Access:** Integrate app endpoint logic so that the mobile app seamlessly talks to existing `main.py` backend and retains the local non-API dependent Ollama features.
