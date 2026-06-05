# Luồng tính của một GCN Layer

## 1. Input graph

Giả sử graph:

```text
0 -- 1 -- 2
```

Feature matrix ban đầu:

\[
X =
\begin{bmatrix}
1 & 0 \\
0 & 1 \\
1 & 1
\end{bmatrix}
\]

- Mỗi dòng là feature của một node.
- `H⁰ = X`

---

## 2. Adjacency matrix

\[
A =
\begin{bmatrix}
0 & 1 & 0 \\
1 & 0 & 1 \\
0 & 1 & 0
\end{bmatrix}
\]

---

## 3. Thêm self-loop

GCN chuẩn thêm self-loop để node giữ lại feature của chính nó.

\[
\hat{A} = A + I
\]

\[
\hat{A} =
\begin{bmatrix}
1 & 1 & 0 \\
1 & 1 & 1 \\
0 & 1 & 1
\end{bmatrix}
\]

---

## 4. Degree matrix

Tính tổng mỗi hàng của `Â`.

\[
\hat{D} =
\begin{bmatrix}
2 & 0 & 0 \\
0 & 3 & 0 \\
0 & 0 & 2
\end{bmatrix}
\]

---

## 5. Normalize adjacency

Công thức chuẩn của GCN:

\[
S = \hat{D}^{-1/2}\hat{A}\hat{D}^{-1/2}
\]

Kết quả xấp xỉ:

\[
S \approx
\begin{bmatrix}
0.5 & 0.408 & 0 \\
0.408 & 0.333 & 0.408 \\
0 & 0.408 & 0.5
\end{bmatrix}
\]

Ý nghĩa:

- Node degree lớn sẽ bị scale xuống.
- Aggregate trở nên ổn định hơn.

---

## 6. Aggregate neighbor features

Aggregate:

\[
M = SX
\]

Thay số:

\[
M =
\begin{bmatrix}
0.5 & 0.408 \\
0.816 & 0.741 \\
0.5 & 0.908
\end{bmatrix}
\]

Ý nghĩa:

- Mỗi node đã nhận thông tin từ neighbor.
- Đây là bước message passing / aggregation.

---

## 7. Linear transform

Giả sử weight matrix:

\[
W =
\begin{bmatrix}
1 & 2 \\
0 & 1
\end{bmatrix}
\]

Tính:

\[
Z = MW
\]

Kết quả:

\[
Z =
\begin{bmatrix}
0.5 & 1.408 \\
0.816 & 2.373 \\
0.5 & 1.908
\end{bmatrix}
\]

---

## 8. Activation

Dùng ReLU:

\[
H^{(1)} = ReLU(Z)
\]

Vì toàn số dương:

\[
H^{(1)} =
\begin{bmatrix}
0.5 & 1.408 \\
0.816 & 2.373 \\
0.5 & 1.908
\end{bmatrix}
\]

Đây là output embedding của GCN layer.

- Mỗi dòng là embedding mới của một node.
- Node đã chứa thông tin neighbor sau 1-hop aggregation.

---

# Công thức tổng quát của GCN

\[
H^{(k+1)} = \sigma(\hat{D}^{-1/2}\hat{A}\hat{D}^{-1/2}H^{(k)}W^{(k)})
\]

Trong đó:

- `H^(k)` : embedding tại layer `k`
- `W^(k)` : weight matrix
- `σ` : activation function
- `Â` : adjacency có self-loop
- `D̂` : degree matrix

---

# Từ embedding ra xác suất classification

Sau GCN:

\[
H =
\begin{bmatrix}
0.5 & 1.408 \\
0.816 & 2.373 \\
0.5 & 1.908
\end{bmatrix}
\]

Thêm classifier:

\[
Z = HW_c + b
\]

`Z` gọi là logits.

Đổi logits thành xác suất bằng softmax:

\[
p_{v,c} = \frac{e^{z_{v,c}}}{\sum_j e^{z_{v,j}}}
\]

Ví dụ:

\[
[3.316, 0.908]
\rightarrow
[0.917, 0.083]
\]

Ý nghĩa:

- 91.7% thuộc class 0
- 8.3% thuộc class 1

---

# Pipeline đầy đủ

```text
Input Features X
        ↓
Adjacency Matrix A
        ↓
Add Self-loop (Â = A + I)
        ↓
Normalize
        ↓
S = D̂^(-1/2) Â D̂^(-1/2)
        ↓
Aggregate
        ↓
M = SX
        ↓
Linear Transform
        ↓
Z = MW
        ↓
Activation
        ↓
H = ReLU(Z)
        ↓
Classifier
        ↓
Softmax
        ↓
Probability
```

