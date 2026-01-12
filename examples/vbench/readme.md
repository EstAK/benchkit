# vbench

Re-implementation of vbench (cf. [References][References]) for benchkit

## Dependencies 

To compile `x264`, the following packages are required :

- `yasm`
- `nasm`

# References

``` bibtex
@article{10.1145/3296957.3173207,
    author = {Lottarini, Andrea and Ramirez, Alex and Coburn, Joel and Kim, Martha A. and Ranganathan, Parthasarathy and Stodolsky, Daniel and Wachsler, Mark},
    title = {vbench: Benchmarking Video Transcoding in the Cloud},
    year = {2018},
    issue_date = {February 2018},
    publisher = {Association for Computing Machinery},
    address = {New York, NY, USA},
    volume = {53},
    number = {2},
    issn = {0362-1340},
    url = {https://doi.org/10.1145/3296957.3173207},
    doi = {10.1145/3296957.3173207},
    abstract = {This paper presents vbench, a publicly available benchmark for cloud video services. We are the first study, to the best of our knowledge, to characterize the emerging video-as-a-service workload. Unlike prior video processing benchmarks, vbench's videos are algorithmically selected to represent a large commercial corpus of millions of videos. Reflecting the complex infrastructure that processes and hosts these videos, vbench includes carefully constructed metrics and baselines. The combination of validated corpus, baselines, and metrics reveal nuanced tradeoffs between speed, quality, and compression. We demonstrate the importance of video selection with a microarchitectural study of cache, branch, and SIMD behavior. vbench reveals trends from the commercial corpus that are not visible in other video corpuses. Our experiments with GPUs under vbench's scoring scenarios reveal that context is critical: GPUs are well suited for live-streaming, while for video-on-demand shift costs from compute to storage and network. Counterintuitively, they are not viable for popular videos, for which highly compressed, high quality copies are required. We instead find that popular videos are currently well-served by the current trajectory of software encoders.},
    journal = {SIGPLAN Not.},
    month = mar,
    pages = {797–809},
    numpages = {13},
    keywords = {accelerator, benchmark, video transcoding}
}
```

