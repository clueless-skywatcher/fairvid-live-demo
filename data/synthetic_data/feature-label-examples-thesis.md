# Mathematical & Empirical Formulation of (X, y) Input-Label Pairs in the Applicant Scoring Thesis

## 1. Executive Overview
In machine learning and automated educational assessment, supervised models are defined by input feature spaces $X$ and target label spaces $y$. Within the Master's Thesis *"Applicant Scoring Model with Explanations and Fairness Mitigation"* (Somiparno Chattopadhyay, 2026) and its foundational literature in Automatic Short Answer Grading (ASAG) and multimodal evaluation, $(X, y)$ pairs operate across four key stages:
1. **Holistic Multimodal Applicant Scoring & Admission Decision**
2. **Interview Answer Grading (ASAG / LLM-as-a-Judge Sub-Task)**
3. **Lexical & Neural Sentence-Embedding ASAG Models**
4. **Demographic & Algorithmic Fairness Verification**

---

## 2. Holistic Multimodal Applicant Scoring Model

### A. Mathematical Formulation
In the primary decision pipeline (an interpretable, standardized Logistic Regression classifier), each applicant $i$ is represented by a late-fused multimodal feature vector $X_i \in \mathbb{R}^d$, mapped to a binary admission outcome $y_i \in \{0, 1\}$:

$$X_i = \Big[ \mathbf{x}_{\text{doc}}, \mathbf{x}_{\text{interview}}, \mathbf{x}_{\text{behavior}} \Big]^T, \quad y_i \in \{0, 1\}$$

* **$X_i$ Components**:
  * $\mathbf{x}_{\text{doc}} = [\text{GPA}, \text{Standardized Test Score}, \text{English Proficiency (IELTS)}, \text{Work Experience}]$
  * $\mathbf{x}_{\text{interview}} = [\text{Mean Answer Grade}, \text{Mean Relevance}, \text{Mean Clarity}, \text{Structure Score}, \text{AI Script Flag Rate}]$
  * $\mathbf{x}_{\text{behavior}} = [\text{Non-verbal Pose/Posture Cues}, \text{Eye Contact Ratio}, \text{Prosodic Speech Features}]$
* **$y_i$ Target**: Binary decision label where $y_i = 1$ denotes **Admitted / Offer Granted** and $y_i = 0$ denotes **Rejected / Denied**.

### B. Concrete Examples of $(X_i, y_i)$

| Applicant Profile | Input Feature Vector $X_i$ | Target Label $y_i$ | Model Prediction & Rationale |
| :--- | :--- | :--- | :--- |
| **Applicant 1** (Strong Academic & Interview) | $\mathbf{x}_{\text{doc}} = [\text{GPA}: 3.85, \text{Test Score}: 88/100, \text{IELTS}: 8.0, \text{Work Exp}: 3\text{ yrs}] \\ \mathbf{x}_{\text{interview}} = [\text{Mean Grade}: 4.75, \text{Relevance}: 4.8, \text{Clarity}: 4.6, \text{AI Flag}: 0] \\ \mathbf{x}_{\text{behavior}} = [\text{Confidence}: \text{High}, \text{Eye Contact}: 85\%]$ | $y = 1$ | **Admitted** ($P(y=1\mid X) = 0.94$). High GPA and clear interview performance drive positive SHAP attribution. |
| **Applicant 2** (AI-Scripted Response) | $\mathbf{x}_{\text{doc}} = [\text{GPA}: 3.20, \text{Test Score}: 72/100, \text{IELTS}: 6.5, \text{Work Exp}: 0\text{ yrs}] \\ \mathbf{x}_{\text{interview}} = [\text{Mean Grade}: 2.10, \text{Relevance}: 2.0, \text{Clarity}: 4.9, \text{AI Flag}: 1] \\ \mathbf{x}_{\text{behavior}} = [\text{Posture}: \text{Rigid}, \text{Prompt Reading Cues}: \text{Detected}]$ | $y = 0$ | **Rejected**. High clarity with off-topic content triggered AI-script detection, reducing score. |
| **Applicant 3** (Low GPA, Rejection Advice) | $\mathbf{x}_{\text{doc}} = [\text{GPA}: 2.40, \text{Test Score}: 65/100, \text{IELTS}: 6.0, \text{Work Exp}: 1\text{ yr}] \\ \mathbf{x}_{\text{interview}} = [\text{Mean Grade}: 3.20, \text{Relevance}: 3.0, \text{Clarity}: 3.5, \text{AI Flag}: 0] \\ \mathbf{x}_{\text{behavior}} = [\text{Normal}]$ | $y = 0$ | **Rejected** ($P(y=1\mid X) = 0.03$). DiCE counterfactual indicates $y \to 1$ requires $\Delta \text{GPA} +0.7$ and $\Delta \text{TestScore} +8$. |

---

## 3. Interview Answer Grading Sub-Task (ASAG / LLM-as-a-Judge)

### A. Mathematical Formulation
For each interview question transcript $s_j$, the perception pipeline passes the response alongside the question prompt $q_j$ and reference scoring rubric $r_j$ to an LLM evaluator:

$$X_{\text{ASAG}} = (q_j, s_j, r_j)$$

$$y_{\text{ASAG}} = \Big( \text{Score}_{\text{overall}} \in [0, 5], \text{Sub-scores}_{\text{relevance, clarity, structure}}, \text{Flag}_{\text{AI\_scripted}} \in \{0, 1\} \Big)$$

### B. Concrete Example
* **Input $X_{\text{ASAG}}$**:
  * **Question ($q_j$)**: *"Explain the time complexity trade-offs between QuickSort and MergeSort."*
  * **Student Response ($s_j$)**: *"MergeSort guarantees O(n log n) time in the worst case using divide-and-conquer, but requires O(n) auxiliary space. QuickSort achieves average O(n log n) time and operates in-place, but degrades to O(n^2) if pivot selection is poor."*
  * **Rubric ($r_j$)**: Key target concepts: worst-case time complexity, auxiliary space complexity, pivot selection, in-place sorting.
* **Target Output $y_{\text{ASAG}}$**:
  * $\text{Score}_{\text{overall}} = 5.0 / 5.0$
  * $\text{Relevance} = 5.0, \quad \text{Clarity} = 5.0, \quad \text{Structure} = 5.0$
  * $\text{Flag}_{\text{AI\_scripted}} = 0$ (Natural delivery)

---

## 4. Classical Lexical & Neural ASAG Models (Thesis Literature Context)

### A. Hamming Distance Lexical Model (Süzen et al., 2020)
* **Formulation**:
  $$X = h(r, m) = |m| - n$$
  where $m$ is the model answer vocabulary, $n$ is the number of matching keywords in student response $r$, and $h(r, m)$ is the Hamming distance.
  $$y = \beta_0 + \beta_1 \cdot h^{\beta_2} \quad \text{or} \quad y \in \{0, 1, 2, 3, 4, 5\}$$
* **Concrete Example**:
  * **Model Vocabulary $m$**: `{"prototype", "portion", "desired", "software", "product", "behavior"}` ($|m| = 6$).
  * **Student Response $r$**: *"It simulates the behavior of portions of the desired software product."* ($n = 4$ keywords present: `behavior`, `portion`, `desired`, `software`).
  * **Input Feature $X$**: $h(r, m) = 6 - 4 = 2$.
  * **Target Label $y$**: Grade = $4.5 / 5.0$ (High correlation $r \approx -0.81$ to $-0.83$ with human marks).

### B. Siamese Sentence-BERT Model (Bonthu et al., PyDSBERT / SPRAG)
* **Formulation**:
  $$X = \Big[ \mathbf{sa}, \mathbf{ra}, |\mathbf{sa} - \mathbf{ra}| \Big]$$
  where $\mathbf{sa} = f(x_{\text{student}})$ and $\mathbf{ra} = f(x_{\text{reference}})$ are mean-pooled sentence embeddings from a domain-adapted DistilBERT model.
  $$y \in \{0, 1\} \quad (0 = \text{Incorrect}, 1 = \text{Correct})$$
* **Concrete Example**:
  * **Student Answer $x_{\text{student}}$**: *"A binary search tree keeps left subtrees smaller and right subtrees greater."*
  * **Reference Answer $x_{\text{reference}}$**: *"BST is a node-based binary tree where left key < parent key < right key."*
  * **Input Feature $X$**: Concatenated 2304-dimensional semantic embedding vector.
  * **Target Label $y$**: $1$ (Correct) — achieves 88.77% accuracy on SPRAG dataset.

---

## 5. Algorithmic Fairness & Bias Verification

### A. Mathematical Formulation
To comply with the EU AI Act high-risk requirements, the feature vector $X$ is paired with protected demographic attributes $A_i \in \{\text{Group}_A, \text{Group}_B\}$ (e.g., Region, Gender) to measure disparity against un-biased ground-truth merit $y_i$:

$$X_{\text{fair}} = (X_i, A_i), \quad y_i \in \{0, 1\}$$

$$\hat{y}_i = \text{Model Predicted Admission Decision}$$

### B. Group Fairness Metrics & Mitigations
* **Disparate Impact Ratio (DIR)**:
  $$\text{DIR} = \frac{P(\hat{y} = 1 \mid A = \text{Unprivileged})}{P(\hat{y} = 1 \mid A = \text{Privileged})} \ge 0.80 \quad (\text{Four-Fifths Rule})$$
* **Mitigated Output Example**:
  * **Unmitigated Model**: DIR = $0.62$ (Fails four-fifths rule due to injected regional test score gap).
  * **Mitigated Model (Pre-processing Proxy Removal + Post-processing Thresholding)**: DIR = $0.85$, $\text{Accuracy} = 85.7\%$, $\text{ROC-AUC} = 0.913$.

---

## 6. Summary Table of $(X, y)$ Across Pipeline Stages

| Pipeline Stage / Model | Input Feature Representation $X$ | Target Label Representation $y$ | Mathematical / Algorithmic Model |
| :--- | :--- | :--- | :--- |
| **Holistic Admission Scoring** | $[\text{GPA}, \text{TestScore}, \text{IELTS}, \text{WorkExp}, \text{ASAG\_Grade}, \text{AI\_Flag}]$ | $y \in \{0, 1\}$ (Admitted / Rejected) | Logistic Regression |
| **ASAG Answer Grading** | $(q_{\text{question}}, s_{\text{transcript}}, r_{\text{rubric}})$ | $y = (\text{Score}_{0-5}, \text{Relevance}, \text{Clarity}, \text{ScriptedFlag})$ | LLM-as-a-Judge / Prompted GPT-4 |
| **Lexical Distance ASAG** | $h(r, m) = |m| - n$ (Hamming Keyword Gap) | $y \in [0, 5]$ (Human / Model Grade) | Non-linear Regression (Süzen et al., 2020) |
| **Neural Similarity ASAG** | $[\mathbf{sa}, \mathbf{ra}, \|\mathbf{sa} - \mathbf{ra}\|]$ Sentence Embeddings | $y \in \{0, 1\}$ (Incorrect / Correct) | Siamese PyDSBERT (Bonthu et al., 2024) |
| **Fairness Mitigation** | $(X_i, A_{\text{region/gender}})$ | $\hat{y}_{\text{mitigated}}$ satisfying DIR $\ge 0.80$ | Pre/Post-Processing (Fairlearn / AIF360) |
