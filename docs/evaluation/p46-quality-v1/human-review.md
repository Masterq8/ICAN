# P4.6 人工复核工作表

当前 reviewer_type=assistant，human_review_status=pending。请核对字段类型、引文支持与遗漏；审核单位为下方 occurrence（从 0 开始），不是去重后的字段名。
修改 manual-review.json 中的判断、理由和字段存在性；保留原始字段哈希。人工完成后填写本人 reviewer、reviewer_type=human 和 human_review_status=completed，再运行 finalize。

## ontology_parser — Joint learning of ontology and semantic parser from text

来源：qasper:1601.00901；版本：06806e4608976fc2fac0a090ac425d5b2b29caf4

证据中应有字段：task, model, dataset, input_setting, training, metric, result
当前遗漏：metric

### 字段 0: task

值：Joint learning of ontology and semantic parser from text

引用：Joint learning of ontology and semantic parser from text

证据 ID：`chunk:2f752ddae79ad754bb23c05e7fe332a47b6f4faef440c94d268e1ef14ec3a0ba`
当前审核：原文支持=False；归类正确=True；建议类型=task
The quoted title does not occur in the cited evidence chunk.

### 字段 1: model

值：the automaton model for institution relation

引用：Figure 6. The automaton model for institution relation.

证据 ID：`chunk:01cbef48e9c45a524bf96e25f36a5dced7f172cb47c856074ef86ff1e4d8c6e7`
当前审核：原文支持=True；归类正确=True；建议类型=model
The automaton model appears verbatim in the figure caption.

### 字段 2: dataset

值：first sentences of Wikipedia pages describing people are taken as a dataset

引用：For experimentation, first sentences of Wikipedia pages describing people are taken as a dataset.

证据 ID：`chunk:b51d3566ce132ffb3c5bc2254b906b74db3c7ed50b48bfaa3cfe1e5df58f7283`
当前审核：原文支持=True；归类正确=True；建议类型=dataset
Wikipedia first sentences are explicitly called a dataset.

### 字段 3: input_setting

值：The grammar was induced on 10.000 random sentences taken from the dataset

引用：The grammar was induced on 10.000 random sentences taken from the dataset described in Section "Datasets" .

证据 ID：`chunk:2f752ddae79ad754bb23c05e7fe332a47b6f4faef440c94d268e1ef14ec3a0ba`
当前审核：原文支持=True；归类正确=False；建议类型=training
Grammar induction on 10,000 sentences is a training setup rather than an input setting.

### 字段 4: training

值：The property assignment was done by the authors.

引用：The property assignment was done by the authors.

证据 ID：`chunk:2f752ddae79ad754bb23c05e7fe332a47b6f4faef440c94d268e1ef14ec3a0ba`
当前审核：原文支持=True；归类正确=True；建议类型=training
Manual property assignment is part of induction setup.

### 字段 5: result

值：time spend for parsing a sentence, which is on average 0.16ms

引用：It is highly correlated with the time spend for parsing a sentence, which is on average 0.16ms.

证据 ID：`chunk:8c61b82465a7a0f2d5f77ed4e9e7bfcf7bbc5104f16fed8fc64ca45744386ff9`
当前审核：原文支持=True；归类正确=True；建议类型=result
Average parsing time is a measured result.

### 字段 6: result

值：More than a quarter of sentences were fully parsed

引用：More than a quarter of sentences were fully parsed, meaning that they do not have any null leaf nodes.

证据 ID：`chunk:8c61b82465a7a0f2d5f77ed4e9e7bfcf7bbc5104f16fed8fc64ca45744386ff9`
当前审核：原文支持=True；归类正确=True；建议类型=result
Fully parsed fraction is a reported result; this duplicate field caused schema rejection.

### 实际输入证据

#### chunk:9fda358c34472ba60aa331b618b7809818f955e614848845cdf7f369f6b4025d

{"paper_id": "1601.00901", "paragraph_index": 1, "section_index": 11}

Victor Francis Hess (24 June 1883 – 17 December 1964) was an Austrian-American physicist, and Nobel laureate in physics, who discovered cosmic rays.

#### chunk:01cbef48e9c45a524bf96e25f36a5dced7f172cb47c856074ef86ff1e4d8c6e7

{"caption_index": 10, "paper_id": "1601.00901"}

Figure 6. The automaton model for institution relation. On the bottom of each node, the fraction of training variable trees that contain this node, is displayed.

#### chunk:2f752ddae79ad754bb23c05e7fe332a47b6f4faef440c94d268e1ef14ec3a0ba

{"paper_id": "1601.00901", "paragraph_index": 0, "section_index": 12}

The grammar was induced on 10.000 random sentences taken from the dataset described in Section "Datasets" . First, a list of 45 seed nodes was constructed. There were 22 domain independent linguistic rules, 17 category rules and 6 top-level rules. The property assignment was done by the authors. In every iteration, the best rule is shown together with the number of nodes it was induced from, and ten of those nodes together with the sentences they appear in. The goal was set to stop the iterative process after two hours. We believe this is the right amount of time to still expect quality feedback from a human user.

#### chunk:b51d3566ce132ffb3c5bc2254b906b74db3c7ed50b48bfaa3cfe1e5df58f7283

{"paper_id": "1601.00901", "paragraph_index": 3, "section_index": 0}

For experimentation, first sentences of Wikipedia pages describing people are taken as a dataset. These sentences are already annotated with links to other pages, which are also instances of DBpedia knowledge base BIBREF9 . Using relations from DBpedia as a training set, several models to predict relations have been trained and evaluated.

#### chunk:8c61b82465a7a0f2d5f77ed4e9e7bfcf7bbc5104f16fed8fc64ca45744386ff9

{"paper_id": "1601.00901", "paragraph_index": 2, "section_index": 12}

The grammar was also tested by parsing a sample of 100.000 test sentences. A few statistic are presented in Table 4 . More than a quarter of sentences were fully parsed, meaning that they do not have any null leaf nodes. Coverage represents the fraction of words in a sentence that were parsed (words that are not in null-nodes). The number of operations shows how many times was the Parse function called during the parsing of a sentences. It is highly correlated with the time spend for parsing a sentence, which is on average 0.16ms. This measurement was done on a single CPU core. Consequently, it is feasible to parse a collection of a million sentences, like our dataset. The same statistics were also calculated on the training set, the numbers are very similar to the test set. The fully parsed % and coverage are even slightly lower than on the test set. Some of the statistics were calculated after each iteration, but only when a non neutral rule was created. The graphs in Figure 5 show how have the statistics changed over the course of the grammar induction. Graph 5 shows that coverage and the fraction of fully parsed sentences are correlated and they grow very rapidly at the beginning, then the growth starts to slow down, which indicates that there is a long tail of unparsed nodes/sentences. In the following section, we present a concept learning method, which deals with the long tail. Furthermore, the number of operations per sentence also slows down (see Graph 5 ) with the number of rules, which gives a positive sign of retaining computational feasibility with the growth of the grammar. Graph 5 somewhat elaborates the dynamics of the grammar induction. In the earlier phase of induction many rules that define the upper structure of the tree are induced. These rules can rapidly increase the depth and number of null nodes, like rule 1 and rule 2 . They also explain the spikes on Graph 5 . Their addition to the grammar causes some rules to emerge on the top of the list with a significantly higher frequency. After these rules are induced the frequency gets back to the previous values and slowly decreases over the long run.

#### chunk:377506fd2b16a1a8f9e1d81d15c0746542de28f766e19c2e777f52c778f392f3

{"caption_index": 9, "paper_id": "1601.00901"}

Table 6. Performance of various relation extraction models.

## speech_recognition — Evaluating the Performance of a Speech Recognition based System

来源：qasper:1601.02543；版本：06806e4608976fc2fac0a090ac425d5b2b29caf4

证据中应有字段：task, model, metric, result, limitation
当前遗漏：task, metric, result

### 字段 0: limitation

值：We will present more experimental results in the final paper.

引用：We will present more experimental results in the final paper.

证据 ID：`chunk:8f23dcb5f429e4cd7c486a1bc701695d82bd7139586629fe67d6c697fc79dba9`
当前审核：原文支持=True；归类正确=True；建议类型=limitation
The excerpt explicitly defers further experimental results.

### 字段 1: model

值：a typical menu based ASR system

引用：Fig. 1. Schematic of a typical menu based ASR system (Wn is spoken word).

证据 ID：`chunk:7d1da55010ca6a9ee84ab2823c103214603a17faf153ce6910f55046207bddf5`
当前审核：原文支持=True；归类正确=True；建议类型=model
The menu-based ASR system is stated in the cited caption.

### 实际输入证据

#### chunk:e2631ae8ae10b636bf04ee68a092cdb37fcd4e62ef0393004a4368ab46ef43bf

{"caption_index": 1, "paper_id": "1601.02543"}

Fig. 2. A typical speech recognition system. In a menu based system the language model is typically the set of words that need to be recognized at a given node.

#### chunk:6f1f53f00e859a74b3c15801ee2edaddf06553369036f6a5cef5754094160983

{"caption_index": 4, "paper_id": "1601.02543"}

Table 2. Distance Measurement for Active Words at Node 1 of the Railway Inquiry System

#### chunk:97a8626a0be6b2ca77651607edce6bc63aa909b77fa4c16c2adc8bde5e331283

{"caption_index": 3, "paper_id": "1601.02543"}

Table 1. List of Active Words at node 1

#### chunk:7d1da55010ca6a9ee84ab2823c103214603a17faf153ce6910f55046207bddf5

{"caption_index": 0, "paper_id": "1601.02543"}

Fig. 1. Schematic of a typical menu based ASR system (Wn is spoken word).

#### chunk:b5281efedc62a91cddd13af231e5aa55a18181a7ae72ed1d97c585acd3d09383

{"caption_index": 2, "paper_id": "1601.02543"}

Fig. 3. Call flow of Indian Railway Inquiry System (Wn is spoken word)

#### chunk:8f23dcb5f429e4cd7c486a1bc701695d82bd7139586629fe67d6c697fc79dba9

{"paper_id": "1601.02543", "paragraph_index": 6, "section_index": 2}

A similar analysis was carried out at other recognition nodes and the active word list was suitably modified to avoid possible confusion between active word pair. This analysis and modification of the list of active words at a node resulted in a significant improvement in the transaction completion rate. We will present more experimental results in the final paper.

## event_extraction — Detecting and Extracting Events from Text Documents

来源：qasper:1601.04012；版本：06806e4608976fc2fac0a090ac425d5b2b29caf4

证据中应有字段：task, dataset, input_setting, training, metric, result, model
当前遗漏：training, model

### 字段 0: task

值：Detecting and Extracting Events from Text Documents

引用：Detecting and Extracting Events from Text Documents

证据 ID：`chunk:865e26540412ac75e8cff86418d81ac462e444caad86463bc7da15be334d9572`
当前审核：原文支持=False；归类正确=True；建议类型=task
The submitted title is not a contiguous quote in the cited table caption.

### 字段 1: dataset

值：ECB+

引用：Cybulska and Vossen use the ECB+ dataset BIBREF191 . The ECB+ corpus contains a new corpus component, consisting of 502 texts, describing different instances of event types.

证据 ID：`chunk:7777cbd552a98bd53abda0a0a1610eee0ee8a4b05163f489da3228612df88582`
当前审核：原文支持=True；归类正确=True；建议类型=dataset
ECB+ is explicitly identified as the dataset.

### 字段 2: metric

值：recall, precision and F-score, MUC, B3, mention-based CEAF, BLANC, and CoNLL F1

引用：They provide results in terms of several metrics: recall, precision and F-score, MUC BIBREF192 , B3 BIBREF184 , mention-based CEAF BIBREF185 , BLANC BIBREF193 , and CoNLL F1 BIBREF194 , and find that the introduction of the granularity concept into similarity computation improves results for every metric.

证据 ID：`chunk:7777cbd552a98bd53abda0a0a1610eee0ee8a4b05163f489da3228612df88582`
当前审核：原文支持=True；归类正确=True；建议类型=metric
The cited paragraph lists coreference metrics.

### 字段 3: metric

值：recall (R), precision (P), and F-score (F)

引用：They report results in terms of recall (R), precision (P), and F-score (F) by employing the mention-based B3 metric BIBREF184 , the entity-based CEAF metric BIBREF185 , and the pairwise F1 (PW) metric.

证据 ID：`chunk:84ad68a362300332e93f141fe4824b8ccc7e22ff35c2bde207620ad4fbb256d1`
当前审核：原文支持=True；归类正确=True；建议类型=metric
The second metric list is valid, but duplicates the metric field.

### 字段 4: result

值：ACE value score of 22.3%

引用：Overall, using the best learned classifiers for the various subtasks, they achieve an ACE value score of 22.3%, where the maximum score is 100%. The value is low, but other systems at the time had comparable performance.

证据 ID：`chunk:e29a1516a1817061cffecb2d37327e3ef5dc10ddcd8955bf02cb469e31124fa4`
当前审核：原文支持=True；归类正确=True；建议类型=result
ACE value 22.3% is a quantitative result.

### 字段 5: result

值：the introduction of the granularity concept into similarity computation improves results for every metric

引用：and find that the introduction of the granularity concept into similarity computation improves results for every metric.

证据 ID：`chunk:7777cbd552a98bd53abda0a0a1610eee0ee8a4b05163f489da3228612df88582`
当前审核：原文支持=True；归类正确=True；建议类型=result
Improvement for every metric is a comparative result.

### 字段 6: result

值：of these three performed among the top ten in TempEval-3 Competition

引用：Inspired by such work, in building the ATT systems, the creators intended to systematically investigate the performance of various models and for each task, they trained twelve models exploring these two dimensions, three of which we submitted for TempEval-3, and of these three performed among the top ten in TempEval-3 Competition.

证据 ID：`chunk:fd20760a84b25c32884c34c15f6833c6ec23dd163a23a31412dffa1e0306359f`
当前审核：原文支持=True；归类正确=True；建议类型=result
Top-ten placement is an experimental result.

### 字段 7: limitation

值：The value is low, but other systems at the time had comparable performance.

引用：The value is low, but other systems at the time had comparable performance.

证据 ID：`chunk:e29a1516a1817061cffecb2d37327e3ef5dc10ddcd8955bf02cb469e31124fa4`
当前审核：原文支持=True；归类正确=False；建议类型=result
Low but comparable performance interprets a result rather than stating a study limitation.

### 字段 8: input_setting

值：three dimensions, three of which we submitted for TempEval-3

引用：for each task, they trained twelve models exploring these two dimensions, three of which we submitted for TempEval-3

证据 ID：`chunk:fd20760a84b25c32884c34c15f6833c6ec23dd163a23a31412dffa1e0306359f`
当前审核：原文支持=False；归类正确=False；建议类型=training
The draft changes two dimensions to three and describes model training/submission, not an input setting.

### 实际输入证据

#### chunk:865e26540412ac75e8cff86418d81ac462e444caad86463bc7da15be334d9572

{"caption_index": 11, "paper_id": "1601.04012"}

Table XI. Evaluation results (recall / precision / f-score for Task 1 in Whole data set (W), Abstracts only (A) and Full papers only (F)

#### chunk:199740b984854bbf21407a446ed8713e8114a648b63dccbcde2e3de24ce4962d

{"paper_id": "1601.04012", "paragraph_index": 3, "section_index": 21}

The BioNLP Shared Tasks provide task definitions, benchmark data and evaluations, and participants compete by developing systems to perform the specified tasks. The theme of BioNLP-ST 2011 was a generalization of the 2009 contest, generalized in three ways: text types, event types, and subject domains. The 2011 event-related tasks were arranged in four tracks: GENIA task (GE) BIBREF197 , Epigenetics and Post-translational Modifications (EPI) BIBREF198 , Infectious Diseases (ID) BIBREF199 , and the Bacteria Track BIBREF200 , BIBREF201 .

#### chunk:7777cbd552a98bd53abda0a0a1610eee0ee8a4b05163f489da3228612df88582

{"paper_id": "1601.04012", "paragraph_index": 27, "section_index": 20}

For the experiments, Cybulska and Vossen use the ECB+ dataset BIBREF191 . The ECB+ corpus contains a new corpus component, consisting of 502 texts, describing different instances of event types. They provide results in terms of several metrics: recall, precision and F-score, MUC BIBREF192 , B3 BIBREF184 , mention-based CEAF BIBREF185 , BLANC BIBREF193 , and CoNLL F1 BIBREF194 , and find that the introduction of the granularity concept into similarity computation improves results for every metric.

#### chunk:84ad68a362300332e93f141fe4824b8ccc7e22ff35c2bde207620ad4fbb256d1

{"paper_id": "1601.04012", "paragraph_index": 17, "section_index": 20}

They report results in terms of recall (R), precision (P), and F-score (F) by employing the mention-based B3 metric BIBREF184 , the entity-based CEAF metric BIBREF185 , and the pairwise F1 (PW) metric. Their experiments for show that both of these models work well when the feature and cluster numbers are treated as free parameters, and the selection of feature values is performed automatically.

#### chunk:fd20760a84b25c32884c34c15f6833c6ec23dd163a23a31412dffa1e0306359f

{"paper_id": "1601.04012", "paragraph_index": 17, "section_index": 19}

Obviously, different sets of features impact on the performance of event recognition and classification BIBREF154 , BIBREF155 , BIBREF156 . In particular, BIBREF157 also examined performance based on different sizes of n-grams in a small scale (n=1,3). Inspired by such work, in building the ATT systems, the creators intended to systematically investigate the performance of various models and for each task, they trained twelve models exploring these two dimensions, three of which we submitted for TempEval-3, and of these three performed among the top ten in TempEval-3 Competition.

#### chunk:e29a1516a1817061cffecb2d37327e3ef5dc10ddcd8955bf02cb469e31124fa4

{"paper_id": "1601.04012", "paragraph_index": 34, "section_index": 19}

The ACE specification provided a way to measure the performance of an event extraction system. The evaluation called ACE value is obtained by scoring each of the component tasks individually and then obtaining a normalized summary value. Overall, using the best learned classifiers for the various subtasks, they achieve an ACE value score of 22.3%, where the maximum score is 100%. The value is low, but other systems at the time had comparable performance.

## mobile_robot — Spatial Concept Acquisition for a Mobile Robot that Integrates Self-Localization and Unsupervised Word Discovery from Spoken Sentences

来源：qasper:1602.01208；版本：06806e4608976fc2fac0a090ac425d5b2b29caf4

证据中应有字段：task, model, input_setting, training, result
当前遗漏：无

### 字段 0: task

值：Learning of spatial concepts

引用：Learning of spatial concepts

证据 ID：`chunk:588e941771c6d3715a86f87eaeb7f9f83013d0a8dce82b3b068eab2fd0e151d7`
当前审核：原文支持=True；归类正确=True；建议类型=task
Learning spatial concepts is explicit.

### 字段 1: model

值：an autonomous mobile robot TurtleBot 2

引用：the effectiveness of the proposed method was tested by using an autonomous mobile robot TurtleBot 2 in a real environment

证据 ID：`chunk:d303a290a805f367c4d367ee208d17649dba4ce0acb3f87a5c965eac1b52bb80`
当前审核：原文支持=True；归类正确=True；建议类型=model
TurtleBot 2 is the experimental system/platform.

### 字段 2: input_setting

值：in a real environment

引用：in a real environment

证据 ID：`chunk:d303a290a805f367c4d367ee208d17649dba4ce0acb3f87a5c965eac1b52bb80`
当前审核：原文支持=True；归类正确=True；建议类型=input_setting
The experiment is explicitly conducted in a real environment.

### 字段 3: training

值：Gibbs sampling Initialize parameters

引用：Gibbs sampling Initialize parameters

证据 ID：`chunk:588e941771c6d3715a86f87eaeb7f9f83013d0a8dce82b3b068eab2fd0e151d7`
当前审核：原文支持=True；归类正确=True；建议类型=training
Gibbs sampling and parameter initialization occur in the learning procedure.

### 字段 4: result

值：A point group of each color to represent each position distribution is drawn on an map of the considered environment

引用：A point group of each color to represent each position distribution is drawn on an map of the considered environment

证据 ID：`chunk:fbc1f7243593c148c351f8c6792133add9c159c5329875ce4668a69f3a2025e8`
当前审核：原文支持=True；归类正确=True；建议类型=result
The figure caption describes the learned position-distribution output.

### 实际输入证据

#### chunk:91b85481ac236bc04036f2a318dad34a9e9a453f521ada048b2ff02a4f6207cb

{"paper_id": "1602.01208", "paragraph_index": 1, "section_index": 14}

Mapping and self-localization are performed by the robot operating system (ROS). The speech recognition system, the microphone, and the unsupervised morphological analyzer were the same as those described in Section SECREF4 .

#### chunk:d303a290a805f367c4d367ee208d17649dba4ce0acb3f87a5c965eac1b52bb80

{"paper_id": "1602.01208", "paragraph_index": 0, "section_index": 14}

In this experiment, the effectiveness of the proposed method was tested by using an autonomous mobile robot TurtleBot 2 in a real environment. Fig. FIGREF70 shows TurtleBot 2 used in the experiments.

#### chunk:588e941771c6d3715a86f87eaeb7f9f83013d0a8dce82b3b068eab2fd0e151d7

{"paper_id": "1602.01208", "paragraph_index": 13, "section_index": 6}

[tb] Learning of spatial concepts [1] INLINEFORM0 , INLINEFORM1 Localization and speech recognition INLINEFORM2 to INLINEFORM3 INLINEFORM4 BIBREF29 the speech signal is observed INLINEFORM5 add INLINEFORM6 to INLINEFORM7 Registering the lattice add INLINEFORM8 to INLINEFORM9 Registering the teaching time Word segmentation using lattices INLINEFORM10 BIBREF22 Gibbs sampling Initialize parameters INLINEFORM11 , INLINEFORM12 , INLINEFORM13 INLINEFORM14 to INLINEFORM15 INLINEFORM16 ( EQREF25 ) INLINEFORM17 ( EQREF26 ) INLINEFORM18 ( EQREF28 ) INLINEFORM19 ( EQREF30 ) INLINEFORM20 ( EQREF31 ) INLINEFORM21 ( EQREF33 ) INLINEFORM22 to INLINEFORM23 INLINEFORM24 ( EQREF34 ) INLINEFORM25

#### chunk:fbc1f7243593c148c351f8c6792133add9c159c5329875ce4668a69f3a2025e8

{"caption_index": 4, "paper_id": "1602.01208"}

Fig. 4. Learning result of the position distribution: A point group of each color to represent each position distribution is drawn on an map of the considered environment. The colors of the point groups are determined randomly. Each balloon shows the index number for each position distribution.

#### chunk:248ac0bc61fec175948974cc9ed08b9656a34407aa053ed9e01ea02d50520206

{"caption_index": 6, "paper_id": "1602.01208"}

Fig. 5. Learning result of the multinomial distributions of the names of places W (top); multinomial distributions of the index of the position distribution φl (bottom): All the words obtained during the experiment are shown.

#### chunk:db7a9f79979ff526d9d30da25ff736f6a0099886e1181c57afce4ed21e6a144b

{"caption_index": 14, "paper_id": "1602.01208"}

Fig. 11. Learning result of each position distribution: A point group of each color denoting each position distribution was drawn on the map. The colors of the point groups were determined randomly. Further, each index number is denoted as it = k.

## many_languages_parser — Many Languages, One Parser

来源：qasper:1602.01595；版本：06806e4608976fc2fac0a090ac425d5b2b29caf4

证据中应有字段：task, model, dataset, input_setting, training, metric, result, limitation
当前遗漏：dataset

### 字段 0: task

值：a single parser trained on a multilingual set of treebanks

引用：We presented MaLOPa, a single parser trained on a multilingual set of treebanks.

证据 ID：`chunk:b717ff6617863bf9912592b3da2e0391b406a4d2eb4c380d8008635b49500a63`
当前审核：原文支持=True；归类正确=False；建议类型=model
A single multilingual parser describes the model, not the parsing task.

### 字段 1: task

值：multilingual set of treebanks

引用：We presented MaLOPa, a single parser trained on a multilingual set of treebanks.

证据 ID：`chunk:b717ff6617863bf9912592b3da2e0391b406a4d2eb4c380d8008635b49500a63`
当前审核：原文支持=True；归类正确=False；建议类型=dataset
A multilingual set of treebanks is dataset information and duplicates task.

### 字段 2: training

值：All embeddings are trained on the same data and use the same number of dimensions (100).

引用：All embeddings are trained on the same data and use the same number of dimensions (100).

证据 ID：`chunk:e958d403c87d08abd2fc250f699f1209e28b596fc211cb8974b85bbbf6644fd2`
当前审核：原文支持=True；归类正确=True；建议类型=training
Embedding training data and dimensionality are training setup.

### 字段 3: model

值：the robust projection multilingual embeddings

引用：Aside from Table 6 , in this paper, we exclusively use the robust projection multilingual embeddings trained in guo:16.

证据 ID：`chunk:e958d403c87d08abd2fc250f699f1209e28b596fc211cb8974b85bbbf6644fd2`
当前审核：原文支持=True；归类正确=True；建议类型=model
Robust-projection multilingual embeddings are a model component.

### 字段 4: metric

值：parsing accuracy

引用：Here, we quantify the degradation in parsing accuracy when language ID and POS tags are only given at training time, but must be predicted at test time.

证据 ID：`chunk:fe5f7598eacaff77f9bf9e0d2bd8f1df77dda9cc92580e8f4cc8495f6a0c5aae`
当前审核：原文支持=True；归类正确=True；建议类型=metric
Parsing accuracy is an evaluation metric.

### 字段 5: input_setting

值：both gold language ID of the input language and gold POS tags are given at test time

引用：In Table 3 , we assume that both gold language ID of the input language and gold POS tags are given at test time. However, this assumption is not realistic in practical applications.

证据 ID：`chunk:fe5f7598eacaff77f9bf9e0d2bd8f1df77dda9cc92580e8f4cc8495f6a0c5aae`
当前审核：原文支持=True；归类正确=True；建议类型=input_setting
Gold language ID and POS tags at test time define the input/evaluation setting.

### 字段 6: limitation

值：this assumption is not realistic in practical applications

引用：However, this assumption is not realistic in practical applications.

证据 ID：`chunk:fe5f7598eacaff77f9bf9e0d2bd8f1df77dda9cc92580e8f4cc8495f6a0c5aae`
当前审核：原文支持=True；归类正确=True；建议类型=limitation
The paper calls the gold-input assumption unrealistic.

### 字段 7: result

值：on average outperforms monolingually-trained parsers for target languages with a treebank

引用：We showed that this parser, equipped with language embeddings and fine-grained POS embeddings, on average outperforms monolingually-trained parsers for target languages with a treebank.

证据 ID：`chunk:b717ff6617863bf9912592b3da2e0391b406a4d2eb4c380d8008635b49500a63`
当前审核：原文支持=True；归类正确=True；建议类型=result
Outperformance over monolingual parsers is a comparative result.

### 字段 8: result

值：our parser outperforms previous cross-lingual multi-source model transfer methods

引用：The value of this sharing is more pronounced in scenarios where the target language's training treebank is small or non-existent, where our parser outperforms previous cross-lingual multi-source model transfer methods.

证据 ID：`chunk:b717ff6617863bf9912592b3da2e0391b406a4d2eb4c380d8008635b49500a63`
当前审核：原文支持=True；归类正确=True；建议类型=result
Outperformance over transfer baselines is another result and duplicates the field.

### 实际输入证据

#### chunk:e958d403c87d08abd2fc250f699f1209e28b596fc211cb8974b85bbbf6644fd2

{"paper_id": "1602.01595", "paragraph_index": 16, "section_index": 10}

All embeddings are trained on the same data and use the same number of dimensions (100). Table 6 illustrates that the three methods perform similarly on this task. Aside from Table 6 , in this paper, we exclusively use the robust projection multilingual embeddings trained in guo:16. The “robust projection” result in Table 6 (which uses 100 dimensions) is comparable to the last row in Table 3 (which uses 50 dimensions).

#### chunk:0fbe23c4f1508f79aba39fc3fbeebf860ed902fdadb1ce4daba15e2205450638

{"paper_id": "1602.01595", "paragraph_index": 2, "section_index": 11}

guo:16 is a transition-based neural-network parsing model based on chen:14. It uses a multilingual embeddings and Brown clusters as lexical features. We compare to the best reported configuration (i.e., the column titled “MULTI-PROJ” in Table 1 of Guo et al., 2016).

#### chunk:e70125330830e4f5309e2cc2014d6a4c43e5eec0601e351d6659f612f1680874

{"paper_id": "1602.01595", "paragraph_index": 0, "section_index": 0}

Developing tools for processing many languages has long been an important goal in NLP BIBREF0 , BIBREF1 , but it was only when statistical methods became standard that massively multilingual NLP became economical. The mainstream approach for multilingual NLP is to design language-specific models. For each language of interest, the resources necessary for training the model are obtained (or created), and separate parameters are fit for each language separately. This approach is simple and grants the flexibility of customizing the model and features to the needs of each language, but it is suboptimal for theoretical and practical reasons. Theoretically, the study of linguistic typology tells us that many languages share morphological, phonological, and syntactic phenomena BIBREF3 ; therefore, the mainstream approach misses an opportunity to exploit relevant supervision from typologically related languages. Practically, it is inconvenient to deploy or distribute NLP tools that are customized for many different languages because, for each language of interest, we need to configure, train, tune, monitor, and occasionally update the model. Furthermore, code-switching or code-mixing (mixing more than one language in the same discourse), which is pervasive in some genres, in particular social media, presents a challenge for monolingually-trained NLP models BIBREF4 .

#### chunk:d401d30013c7242819c2ae9e70c246edac7914515909871b77a9c1ffa74b8f09

{"paper_id": "1602.01595", "paragraph_index": 1, "section_index": 11}

zhang:15 is a graph-based arc-factored parsing model with a tensor-based scoring function. It takes typological properties of a language as input. We compare to the best reported configuration (i.e., the column titled “OURS” in Table 5 of Zhang and Barzilay, 2015).

#### chunk:b717ff6617863bf9912592b3da2e0391b406a4d2eb4c380d8008635b49500a63

{"paper_id": "1602.01595", "paragraph_index": 0, "section_index": 13}

We presented MaLOPa, a single parser trained on a multilingual set of treebanks. We showed that this parser, equipped with language embeddings and fine-grained POS embeddings, on average outperforms monolingually-trained parsers for target languages with a treebank. This pattern of results is quite encouraging. Although languages may share underlying syntactic properties, individual parsing models must behave quite differently, and our model allows this while sharing parameters across languages. The value of this sharing is more pronounced in scenarios where the target language's training treebank is small or non-existent, where our parser outperforms previous cross-lingual multi-source model transfer methods.

#### chunk:fe5f7598eacaff77f9bf9e0d2bd8f1df77dda9cc92580e8f4cc8495f6a0c5aae

{"paper_id": "1602.01595", "paragraph_index": 9, "section_index": 10}

In Table 3 , we assume that both gold language ID of the input language and gold POS tags are given at test time. However, this assumption is not realistic in practical applications. Here, we quantify the degradation in parsing accuracy when language ID and POS tags are only given at training time, but must be predicted at test time. We do not use fine-grained POS tags in these experiments because some languages use a very large fine-grained POS tag set (e.g., 866 unique tags in Portuguese).

## contextual_lstm — Contextual LSTM (CLSTM) models for Large scale NLP tasks

来源：qasper:1602.06291；版本：06806e4608976fc2fac0a090ac425d5b2b29caf4

证据中应有字段：task, model, dataset, input_setting, training, metric, result, limitation
当前遗漏：model

### 字段 0: task

值：word prediction task, where the goal is to predict the next word in a sentence given the words and context (captured via topic) seen previously

引用：we focus first on the word prediction task, where the goal is to predict the next word in a sentence given the words and context (captured via topic) seen previously.

证据 ID：`chunk:edbd3050496d35ced5e7681f5b6e91ec0ff3233284c6b25e86fe0ae2a017dce5`
当前审核：原文支持=True；归类正确=True；建议类型=task
Next-word prediction is explicit.

### 字段 1: dataset

值：whole English corpus from Wikipedia (snapshot from 2014/09/17)

引用：we used the whole English corpus from Wikipedia (snapshot from 2014/09/17). There were 4.7 million documents in the Wikipedia dataset

证据 ID：`chunk:9b75f3f7cfb83772129882dda1eb796bdccc594a209a42632bd2565d014d6574`
当前审核：原文支持=True；归类正确=True；建议类型=dataset
Wikipedia corpus is a dataset.

### 字段 2: dataset

值：internal Google News English corpus

引用：We also ran experiments on a sample of documents taken from a recent (2015/07/06) snapshot of the internal Google News English corpus.

证据 ID：`chunk:90d72bc5d815517b673fbab16aef3f4e0d5e9614b0d50d62ab9db2818e932867`
当前审核：原文支持=True；归类正确=True；建议类型=dataset
Google News corpus is another dataset and duplicates the field.

### 字段 3: input_setting

值：We created the vocabulary from the words in the training data, filtering out words that occurred less than a particular threshold count in the total dataset (threshold was 200 for Wikipedia). This resulted in a vocabulary with 129K unique terms

引用：We created the vocabulary from the words in the training data, filtering out words that occurred less than a particular threshold count in the total dataset (threshold was 200 for Wikipedia). This resulted in a vocabulary with 129K unique terms, giving us an out-of-vocabulary rate of 3% on the validation dataset.

证据 ID：`chunk:2b3e32cbaa2c01ab8f65256b76ef76249ba85d2a4f709c2dd89faad955bf28c5`
当前审核：原文支持=True；归类正确=True；建议类型=input_setting
Vocabulary filtering is an input preprocessing setting.

### 字段 4: training

值：80% was used as train, 10% as validation and 10% as test set

引用：which we randomly divided into 3 parts: 80% was used as train, 10% as validation and 10% as test set.

证据 ID：`chunk:9b75f3f7cfb83772129882dda1eb796bdccc594a209a42632bd2565d014d6574`
当前审核：原文支持=True；归类正确=True；建议类型=training
Train/validation/test split is experimental setup.

### 字段 5: metric

值：perplexity

引用：it gave a perplexity of $\approx $ 80 on the validation set

证据 ID：`chunk:4533b7ea0f51cf6d3e9b93068bd8d3f932f2bba598bd1826ed8c36093dabeeb6`
当前审核：原文支持=True；归类正确=True；建议类型=metric
Perplexity is the metric.

### 字段 6: result

值：a distributed n-gram model with “stupid backoff” smoothing BIBREF45 on the Wikipedia dataset, and it gave a perplexity of $\approx $ 80 on the validation set

引用：we also trained a distributed n-gram model with “stupid backoff” smoothing BIBREF45 on the Wikipedia dataset, and it gave a perplexity of $\approx $ 80 on the validation set.

证据 ID：`chunk:4533b7ea0f51cf6d3e9b93068bd8d3f932f2bba598bd1826ed8c36093dabeeb6`
当前审核：原文支持=True；归类正确=True；建议类型=result
Perplexity near 80 is a result.

### 字段 7: result

值：on the Google News data (from a particular snapshot) the KN smoothed n-gram model gave a perplexity of 74 (using 5-grams)

引用：on the Google News data (from a particular snapshot) the KN smoothed n-gram model gave a perplexity of 74 (using 5-grams).

证据 ID：`chunk:4533b7ea0f51cf6d3e9b93068bd8d3f932f2bba598bd1826ed8c36093dabeeb6`
当前审核：原文支持=True；归类正确=True；建议类型=result
Perplexity 74 is another result and duplicates the field.

### 字段 8: limitation

值：We did not train a n-gram model with Knesner-Ney (KN) smoothing on the Wikipedia data

引用：We did not train a n-gram model with Knesner-Ney (KN) smoothing on the Wikipedia data

证据 ID：`chunk:4533b7ea0f51cf6d3e9b93068bd8d3f932f2bba598bd1826ed8c36093dabeeb6`
当前审核：原文支持=True；归类正确=True；建议类型=limitation
The missing KN Wikipedia experiment is an explicit limitation of the comparison.

### 实际输入证据

#### chunk:9b75f3f7cfb83772129882dda1eb796bdccc594a209a42632bd2565d014d6574

{"paper_id": "1602.06291", "paragraph_index": 5, "section_index": 5}

For our experiments, we used the whole English corpus from Wikipedia (snapshot from 2014/09/17). There were 4.7 million documents in the Wikipedia dataset, which we randomly divided into 3 parts: 80% was used as train, 10% as validation and 10% as test set. Some relevant statistics of the train, test and validation data sets of the Wikipedia corpus are given in Table 1 .

#### chunk:edbd3050496d35ced5e7681f5b6e91ec0ff3233284c6b25e86fe0ae2a017dce5

{"paper_id": "1602.06291", "paragraph_index": 0, "section_index": 2}

Of the three different tasks outlined in Section "Model" , we focus first on the word prediction task, where the goal is to predict the next word in a sentence given the words and context (captured via topic) seen previously.

#### chunk:9b70cf96aae829bcd048161cc955fe52cc1b7613572c19f89d3b7e8b1eff615f

{"paper_id": "1602.06291", "paragraph_index": 7, "section_index": 5}

For different types of text segments (e.g., segment, sentence, paragraph) in the training data, we queried HTM and got the most likely topic category. That gave us a total of $\approx $ 1600 topic categories in the dataset.

#### chunk:90d72bc5d815517b673fbab16aef3f4e0d5e9614b0d50d62ab9db2818e932867

{"paper_id": "1602.06291", "paragraph_index": 0, "section_index": 14}

We also ran experiments on a sample of documents taken from a recent (2015/07/06) snapshot of the internal Google News English corpus. This subset had 4.3 million documents, which we divided into train, test and validation datasets. Some relevant statistics of the datasets are given in Table 6 . We filtered out words that occurred less than 100 times, giving us a vocabulary of 100K terms.

#### chunk:2b3e32cbaa2c01ab8f65256b76ef76249ba85d2a4f709c2dd89faad955bf28c5

{"paper_id": "1602.06291", "paragraph_index": 6, "section_index": 5}

We created the vocabulary from the words in the training data, filtering out words that occurred less than a particular threshold count in the total dataset (threshold was 200 for Wikipedia). This resulted in a vocabulary with 129K unique terms, giving us an out-of-vocabulary rate of 3% on the validation dataset.

#### chunk:4533b7ea0f51cf6d3e9b93068bd8d3f932f2bba598bd1826ed8c36093dabeeb6

{"paper_id": "1602.06291", "paragraph_index": 12, "section_index": 5}

Note that we also trained a distributed n-gram model with “stupid backoff” smoothing BIBREF45 on the Wikipedia dataset, and it gave a perplexity of $\approx $ 80 on the validation set. We did not train a n-gram model with Knesner-Ney (KN) smoothing on the Wikipedia data, but on the Google News data (from a particular snapshot) the KN smoothed n-gram model gave a perplexity of 74 (using 5-grams).

## russian_twitter — Gibberish Semantics: How Good is Russian Twitter in Word Semantic Similarity Task?

来源：qasper:1602.08741；版本：06806e4608976fc2fac0a090ac425d5b2b29caf4

证据中应有字段：task, model, dataset, input_setting, training, metric, result, limitation
当前遗漏：无

### 字段 0: task

值：word semantic similarity task

引用：We use Word2Vec to obtain word vectors from Twitter corpus.

证据 ID：`chunk:116ffeef877e1874cafbdd9c085459621e1b0cff5d588015cb1990a15a3934fc`
当前审核：原文支持=False；归类正确=True；建议类型=task
The cited quote discusses Word2Vec but does not contain the submitted task phrase.

### 字段 1: model

值：Skip-gram

引用：In our study CBOW always performs worse than Skip-gram, hence we describe only results with Skip-gram model.

证据 ID：`chunk:116ffeef877e1874cafbdd9c085459621e1b0cff5d588015cb1990a15a3934fc`
当前审核：原文支持=True；归类正确=True；建议类型=model
Skip-gram is explicit.

### 字段 2: dataset

值：HJ-dataset

引用：It produces the set of vectors, which we then query to obtain similarity between word vectors, in order to compute the correlation with HJ-dataset.

证据 ID：`chunk:38858a2f373bf48c291123bdd7343f365ed49b1debfad4bb98df0a1575538b3f`
当前审核：原文支持=True；归类正确=True；建议类型=dataset
HJ-dataset is explicit.

### 字段 3: input_setting

值：We train our model subsequently with 1, 7 and 15 days of Twitter data

引用：We train our model subsequently with 1, 7 and 15 days of Twitter data (each starting with 07/21 and followed by subsequent days) .

证据 ID：`chunk:4727c9bfb55b5dbcb0a7556a4edfcf94d2c2d2d16a62c6f9a625f18fe3a1fc03`
当前审核：原文支持=True；归类正确=False；建议类型=training
The 1/7/15-day training-corpus comparison is training setup, consistently with the ontology induction-data label; actual line-by-line input preprocessing is separately present.

### 字段 4: training

值：vector size of 300, min-freq of 40, context size of 5 and downsampling of 1e-3

引用：We fix parameters for the model with following values: vector size of 300, min-freq of 40, context size of 5 and downsampling of 1e-3.

证据 ID：`chunk:4727c9bfb55b5dbcb0a7556a4edfcf94d2c2d2d16a62c6f9a625f18fe3a1fc03`
当前审核：原文支持=True；归类正确=True；建议类型=training
Vector size, frequency, context and downsampling parameters are training setup.

### 字段 5: metric

值：Spearman coefficient

引用：To compute correlation we use Spearman coefficient, since it was used as accuracy measure in RUSSE BIBREF4 .

证据 ID：`chunk:38858a2f373bf48c291123bdd7343f365ed49b1debfad4bb98df0a1575538b3f`
当前审核：原文支持=True；归类正确=True；建议类型=metric
Spearman coefficient is explicit.

### 字段 6: result

值：the best result belongs to 7-day corpus with 0.56 correlation with HJ-dataset, and 15-day corpus has a little less, 0.55

引用：In this experiment the best result belongs to 7-day corpus with 0.56 correlation with HJ-dataset, and 15-day corpus has a little less, 0.55.

证据 ID：`chunk:4727c9bfb55b5dbcb0a7556a4edfcf94d2c2d2d16a62c6f9a625f18fe3a1fc03`
当前审核：原文支持=True；归类正确=True；建议类型=result
0.56 and 0.55 correlations are results.

### 字段 7: result

值：training model with vector size of 600 on full Twitter corpus (15 days) shows the best result of 0.59

引用：Indeed, training model with vector size of 600 on full Twitter corpus (15 days) shows the best result of 0.59.

证据 ID：`chunk:4727c9bfb55b5dbcb0a7556a4edfcf94d2c2d2d16a62c6f9a625f18fe3a1fc03`
当前审核：原文支持=True；归类正确=True；建议类型=result
0.59 is another result and duplicates the field.

### 字段 8: limitation

值：in order to achieve better results with Word2Vec one should increase both corpus and vector sizes

引用：This can be explained by following: in order to achieve better results with Word2Vec one should increase both corpus and vector sizes.

证据 ID：`chunk:4727c9bfb55b5dbcb0a7556a4edfcf94d2c2d2d16a62c6f9a625f18fe3a1fc03`
当前审核：原文支持=True；归类正确=True；建议类型=limitation
The need for larger corpus and vectors is a stated constraint/recommendation.

### 实际输入证据

#### chunk:51251d9d96299342452459d868fdffdeba70d68ee5a855a06ff97eeed791e5fe

{"paper_id": "1602.08741", "paragraph_index": 0, "section_index": 7}

In this section we describe properties of data obtained from Twitter, describe experiment protocols and results.

#### chunk:97aa3f51084fa6e16b17b735c4116277e6b50d010daa0003cba3f34a61ea533c

{"caption_index": 4, "paper_id": "1602.08741"}

Table 5. Comparison with current single-corpus trained results

#### chunk:38858a2f373bf48c291123bdd7343f365ed49b1debfad4bb98df0a1575538b3f

{"paper_id": "1602.08741", "paragraph_index": 1, "section_index": 6}

There are several implementations of Word2Vec available, including original C utility and a Python library gensim. We use the latter one as we find it more convenient. Output of Tomita Parser is fed directly line-by-line to the model. It produces the set of vectors, which we then query to obtain similarity between word vectors, in order to compute the correlation with HJ-dataset. To compute correlation we use Spearman coefficient, since it was used as accuracy measure in RUSSE BIBREF4 .

#### chunk:116ffeef877e1874cafbdd9c085459621e1b0cff5d588015cb1990a15a3934fc

{"paper_id": "1602.08741", "paragraph_index": 0, "section_index": 6}

We use Word2Vec to obtain word vectors from Twitter corpus. In this model word vectors are initialized randomly for each unique word and are fed to a sort of neural network. Authors of Word2Vec propose two different models: Skip-gram and CBOW. The first one is trained to predict the context of the word given just the word vector itself. The second one is somewhat opposite: it is trained to predict the word vector given its context. In our study CBOW always performs worse than Skip-gram, hence we describe only results with Skip-gram model. Those models have several training parameters, namely: vector size, size of vocabulary (or minimal frequency of a word), context size, threshold of downsampling, amount of training epochs. We choose vector size based on size of corpus. We use “context size” as “number of tokens before or after current token”. In all experiments presented in this paper we use one training epoch.

#### chunk:4727c9bfb55b5dbcb0a7556a4edfcf94d2c2d2d16a62c6f9a625f18fe3a1fc03

{"paper_id": "1602.08741", "paragraph_index": 0, "section_index": 9}

Word2Vec model was designed to be trained on large corpora. There are results of training it in reasonable time with corpus size of 1 billion of tokens BIBREF2 . It was mentioned that accuracy of estimated word vectors improves with size of corpus. Twitter provides an enormous amount of data, thus it is a perfect job for Word2Vec. We fix parameters for the model with following values: vector size of 300, min-freq of 40, context size of 5 and downsampling of 1e-3. We train our model subsequently with 1, 7 and 15 days of Twitter data (each starting with 07/21 and followed by subsequent days) . The largest corpus of 15 days contains 580M tokens. Results of training are shown in Table 3. In this experiment the best result belongs to 7-day corpus with 0.56 correlation with HJ-dataset, and 15-day corpus has a little less, 0.55. This can be explained by following: in order to achieve better results with Word2Vec one should increase both corpus and vector sizes. Indeed, training model with vector size of 600 on full Twitter corpus (15 days) shows the best result of 0.59. It is also worth noting that number of "missing" pairs is negligible in 7-days corpus: the only missing word (and pair) is "russianйель", Yale, the name of university in the USA. There are no "missing" words in 15-days corpus.

#### chunk:72366a903d6fb4afa1e0c1e7fc0a611a00e3ee49ecd8c8b581a10666da629788

{"paper_id": "1602.08741", "paragraph_index": 1, "section_index": 9}

Training the model on 15-days corpus took 8 hours on our machine with 2 cores and 4Gb of RAM. We have an intuition that further improvements are possible with larger corpus. Comparing our results to ones reported by RUSSE participants, we conclude that our best result of 0.598 is comparable to other results, as it (virtually) encloses the top-10 of results. However, best submission of RUSSE has huge gap in accuracy of 0.16, compared to our Twitter corpus. Having in mind that best results in RUSSE combine several corpora, it is reasonable to compare Twitter results to other single-corpus results. For convenience we replicate results for these corpora, originally presented in BIBREF4 , alongside with our result in Table 5. Given these considerations we conclude that with size of Twitter corpus of 500M one can achieve reasonably good results on task of word semantic similarity.

## entity_coreference — Unsupervised Ranking Model for Entity Coreference Resolution

来源：qasper:1603.04553；版本：06806e4608976fc2fac0a090ac425d5b2b29caf4

证据中应有字段：task, model, dataset, input_setting, training, metric, result
当前遗漏：无

### 字段 0: task

值：entity coreference resolution

引用：We proposed a new generative, unsupervised ranking model for entity coreference resolution

证据 ID：`chunk:fc5ec8894c202c3224e6dc5c2c8bb4e3cd19b27b60895325d4da659138cd7fd6`
当前审核：原文支持=True；归类正确=True；建议类型=task
Entity coreference resolution is explicit.

### 字段 1: model

值：a new generative, unsupervised ranking model for entity coreference resolution

引用：We proposed a new generative, unsupervised ranking model for entity coreference resolution into which we introduced resolution mode variables to distinguish mentions resolved by different categories of information.

证据 ID：`chunk:fc5ec8894c202c3224e6dc5c2c8bb4e3cd19b27b60895325d4da659138cd7fd6`
当前审核：原文支持=True；归类正确=True；建议类型=model
The generative unsupervised ranking model is explicit.

### 字段 2: dataset

值：APW and NYT sections of Gigaword Corpus

引用：we select the APW and NYT sections of Gigaword Corpus (years 1994-2010) BIBREF20 to train the model

证据 ID：`chunk:146030edd8a379d47f90d3dfa94c202a83c3fa49a96e8b2966a57be7b20683b6`
当前审核：原文支持=True；归类正确=True；建议类型=dataset
Gigaword APW/NYT is training data.

### 字段 3: dataset

值：CoNLL-2012 shared task

引用：The development and test data are the English data from the CoNLL-2012 shared task BIBREF0 , which is derived from the OntoNotes corpus BIBREF21

证据 ID：`chunk:146030edd8a379d47f90d3dfa94c202a83c3fa49a96e8b2966a57be7b20683b6`
当前审核：原文支持=True；归类正确=True；建议类型=dataset
CoNLL-2012/OntoNotes is evaluation data and duplicates the field.

### 字段 4: training

值：we select the APW and NYT sections of Gigaword Corpus (years 1994-2010) BIBREF20 to train the model

引用：Due to the availability of readily parsed data, we select the APW and NYT sections of Gigaword Corpus (years 1994-2010) BIBREF20 to train the model. Following previous work BIBREF3 , we remove duplicated documents and the documents which include fewer than 3 sentences.

证据 ID：`chunk:146030edd8a379d47f90d3dfa94c202a83c3fa49a96e8b2966a57be7b20683b6`
当前审核：原文支持=True；归类正确=True；建议类型=training
Training corpus selection and document filtering are explicit.

### 字段 5: input_setting

值：Our system is evaluated with automatically extracted mentions on the version of the data with automatic preprocessing information

引用：Our system is evaluated with automatically extracted mentions on the version of the data with automatic preprocessing information (e.g., predicted parse trees).

证据 ID：`chunk:146030edd8a379d47f90d3dfa94c202a83c3fa49a96e8b2966a57be7b20683b6`
当前审核：原文支持=True；归类正确=True；建议类型=input_setting
Automatic mentions and predicted preprocessing define evaluation input.

### 字段 6: metric

值：MUC BIBREF22 , B $^{3}$ BIBREF23 , and Entity-based CEAF (CEAF $_e$ )

引用：We evaluate our model on three measures widely used in the literature: MUC BIBREF22 , B $^{3}$ BIBREF23 , and Entity-based CEAF (CEAF $_e$ ) BIBREF24 . In addition, we also report results on another two popular metrics: Mention-based CEAF (CEAF $_m$ ) and BLANC BIBREF25 .

证据 ID：`chunk:de09a5eed4ccdd12a35d3368f3e91ab1e675d7f07d01b7207ee5f3a2338ae077`
当前审核：原文支持=True；归类正确=True；建议类型=metric
MUC/B3/CEAF metrics are explicit.

### 字段 7: metric

值：CoNLL F1 score

引用：our model achieves improvements of 2.93% and 3.01% on CoNLL F1 score over the Stanford system

证据 ID：`chunk:197bc3288848e9d890d53d47d0137fee4748976344c247edb7dffd85d4093c10`
当前审核：原文支持=True；归类正确=True；建议类型=metric
CoNLL F1 is a metric and duplicates the field.

### 字段 8: result

值：improvements of 2.93% and 3.01% on CoNLL F1 score over the Stanford system

引用：our model achieves improvements of 2.93% and 3.01% on CoNLL F1 score over the Stanford system, the winner of the CoNLL 2011 shared task, on the CoNLL 2012 development and test sets, respectively. The improvements on CoNLL F1 score over the Multigraph model are 1.41% and 1.77% on the development and test sets, respectively. Comparing with the MIR model, we obtain significant improvements of 2.62% and 3.02% on CoNLL F1 score.

证据 ID：`chunk:197bc3288848e9d890d53d47d0137fee4748976344c247edb7dffd85d4093c10`
当前审核：原文支持=True；归类正确=True；建议类型=result
Reported percentage improvements over three baselines are results.

### 实际输入证据

#### chunk:de09a5eed4ccdd12a35d3368f3e91ab1e675d7f07d01b7207ee5f3a2338ae077

{"paper_id": "1603.04553", "paragraph_index": 1, "section_index": 7}

Evaluation Metrics. We evaluate our model on three measures widely used in the literature: MUC BIBREF22 , B $^{3}$ BIBREF23 , and Entity-based CEAF (CEAF $_e$ ) BIBREF24 . In addition, we also report results on another two popular metrics: Mention-based CEAF (CEAF $_m$ ) and BLANC BIBREF25 . All the results are given by the latest version of CoNLL-2012 scorer

#### chunk:146030edd8a379d47f90d3dfa94c202a83c3fa49a96e8b2966a57be7b20683b6

{"paper_id": "1603.04553", "paragraph_index": 0, "section_index": 7}

Datasets. Due to the availability of readily parsed data, we select the APW and NYT sections of Gigaword Corpus (years 1994-2010) BIBREF20 to train the model. Following previous work BIBREF3 , we remove duplicated documents and the documents which include fewer than 3 sentences. The development and test data are the English data from the CoNLL-2012 shared task BIBREF0 , which is derived from the OntoNotes corpus BIBREF21 . The corpora statistics are shown in Table 2 . Our system is evaluated with automatically extracted mentions on the version of the data with automatic preprocessing information (e.g., predicted parse trees).

#### chunk:fc5ec8894c202c3224e6dc5c2c8bb4e3cd19b27b60895325d4da659138cd7fd6

{"paper_id": "1603.04553", "paragraph_index": 0, "section_index": 9}

We proposed a new generative, unsupervised ranking model for entity coreference resolution into which we introduced resolution mode variables to distinguish mentions resolved by different categories of information. Experimental results on the data from CoNLL-2012 shared task show that our system significantly improves the accuracy on different evaluation metrics over the baseline systems.

#### chunk:197bc3288848e9d890d53d47d0137fee4748976344c247edb7dffd85d4093c10

{"paper_id": "1603.04553", "paragraph_index": 0, "section_index": 8}

Table 3 illustrates the results of our model together as baseline with two deterministic systems, namely Stanford: the Stanford system BIBREF10 and Multigraph: the unsupervised multigraph system BIBREF26 , and one unsupervised system, namely MIR: the unsupervised system using most informative relations BIBREF27 . Our model outperforms the three baseline systems on all the evaluation metrics. Specifically, our model achieves improvements of 2.93% and 3.01% on CoNLL F1 score over the Stanford system, the winner of the CoNLL 2011 shared task, on the CoNLL 2012 development and test sets, respectively. The improvements on CoNLL F1 score over the Multigraph model are 1.41% and 1.77% on the development and test sets, respectively. Comparing with the MIR model, we obtain significant improvements of 2.62% and 3.02% on CoNLL F1 score.

#### chunk:cbfe5c1a60cbda1815804692bbd12a99e451ecff5c9202ff6f6a2766bebc55c8

{"caption_index": 2, "paper_id": "1603.04553"}

Table 3: F1 scores of different evaluation metrics for our model, together with two deterministic systems and one unsupervised system as baseline (above the dashed line) and seven supervised systems (below the dashed line) for comparison on CoNLL 2012 development and test datasets.

#### chunk:dfc76850a461df7ac45bc0252ac7a0d641375e44b1d9ad433b2479992f8d5c23

{"paper_id": "1603.04553", "paragraph_index": 7, "section_index": 10}

where $L_{jk}$ can be calculated by $
{\small \begin{array}{rcl}
L_{jk} & = & \sum \limits _{C, c_j=k} \tilde{P}(C|D) = \frac{\sum \limits _{C, c_j=k} \tilde{P}(C, D)}{\sum \limits _{C} \tilde{P}(C, D)} \\
& = & \frac{\sum \limits _{C, c_j=k}\prod \limits _{i = 1}^{n}\tilde{\theta }(m_i, m_{c_i}, c_i, i, \pi _i)}{\sum \limits _{C}\prod \limits _{i = 1}^{n}\tilde{\theta }(m_i, m_{c_i}, c_i, i, \pi _i)} \\
& = & \frac{\tilde{\theta }(m_j, m_k, k, j, \pi _j)\sum \limits _{C(-j)}\tilde{P}(C(-j)|D)}{\sum \limits _{i=0}^{j-1}\tilde{\theta }(m_j, m_i, i, j, \pi _j)\sum \limits _{C(-j)}\tilde{P}(C(-j)|D)} \\
& = & \frac{\tilde{\theta }(m_j, m_k, k, j, \pi _j)}{\sum \limits _{i=0}^{j-1}\tilde{\theta }(m_j, m_i, i, j, \pi _j)} \\
& = & \frac{\tilde{t}(m_j|m_k, \pi _j) \tilde{q}(k|\pi _j, j) \tilde{\tau }(\pi _j|j)}{\sum \limits _{i=0}^{j-1}\tilde{t}(m_j|m_i, \pi _j) \tilde{q}(i|\pi _j, j) \tilde{\tau }(\pi _j|j)} \\
& = & \frac{\tilde{t}(m_j|m_k, \pi _j) \tilde{q}(k|\pi _j, j)}{\sum \limits _{i=0}^{j-1}\tilde{t}(m_j|m_i, \pi _j) \tilde{q}(i|\pi _j, j)}
\end{array}}
$
