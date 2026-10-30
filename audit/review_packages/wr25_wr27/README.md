# WR-25／26／27新固定版本独立复审

请固定本目录所在PR最终Git提交，记录 `git rev-parse HEAD`、全量source、稳定execution、implementation及deployment身份。原审核版本为ccad61d；实际云端执行仍为7fc5ef2。本轮新候选未部署或真实运行，旧读回、编译或原生失败不能证明当前版本云端成功。

先读AGENTS.md、config/development.json、章程、预算、字典、时间分区、当前review_tracking/readiness、docs/review/wr25-wr27.md及原独立正式报告。原WR-22／23／24的局部通过按ccad范围保留，不能由开发者扩展为新修补通过或关闭新发现。

仅在新隔离源码及合成账本执行。运行 `python -B tools/stages.py verify`、最终只读 `python -B tools/review_metadata.py`，额外独立构造已知答案／边界，不改断言迎合产品。需要的Git基线须本地已有，不自动拉取远程。不要执行可能改真实账本的归档准入／结算脚本，不访问QC或市场数据、不调用Research／LEAN／模型／交易；工程停止门和最终测试关闭。

1. 原7场景WR25/26 MRE使用归档原创fixture，不导入开发者测试。先对旧固定源码复现unmapped/future/missing误过，再对新版本检查正常纳入、None／未映射分类、明确ETF和未上市、当前缺失、未来可知。所有新反例必须通过正常store_certification_table和audit入口，不能只测内部helper。分类枚举封闭，未知不能当排除。
2. 覆盖已知老listed／过去明确排除但有限区间到期／当前段缺失／晚可知与全缺流动性的组合；映射到期不是退市，不允许未来值回填。当前记录在形成时点恰好可知与晚一微秒要区分；只有future主表且当时未曾可知的SID不能被未来库存创造过去义务。明确且及时的排除正控保持。
3. 保持原WR20 IPO、WR22连续历史／完整性、None／分类未知、断档／重叠、raw／refs／counts、summary私有重算及全部正式认证false。数据观测符合不等于供应商真实性、全历史US200或财务版本认证。
4. WR27必须用真实不同的两个隔离源码目录：从S工具执行`--root T`，正确T哈希通过、错误S哈希拒绝；默认S及相对路径保持。budget、journal、历史、diff与源码哈希都绑同一root，不能靠改cwd、全局ROOT或关闭--root取巧。保留原固定版本MRE和各次原输出，新的基线／版本适配明确记载。
5. 回归受影响阶段0／1、WR11至WR24、原准入／失败／原attempt恢复、同步写异常、实际进程单次许可、worker严格EOF、原生错误／未知载体、采集缓存、PIT、标签、数值、预算及幂等。原f5d错误在隔离副本15→17→17，真实17事件与预算不写入、不退款。

开发证据清单和结果见 developer_outputs_manifest.json、developer_verification.json。原独立包采用选择性归档，完整ZIP及省略项按原路径/hash引用；原件按局部.gitattributes保持。首次失败、测试夹具适配、修正及不同源码身份须分开，开发者重放不等于独立批准，套件有重叠不合计为独有总数。

交付正式JSON及可读报告，逐项写固定提交、环境、实际命令／次数、首次结果、可复现发现、覆盖和证据不足。分别判断三项修补、模块、阶段2、数据和金融证据；真实成功联合链、旧worker差异及完整数据认证仍单列，不能据软件测试宣告阶段3–7通过。预算7/12、10/20、1/16及正式研究／自动GPT／交易／最终测试关闭状态保持。

交付前预检曾发现复制的隔离Git索引为非UTF-8二进制临时工件；原件保留在忽略的开发工作目录，其路径、大小和raw hash见 verification/omitted_working_artifacts.json，首次错误及修正在 publication_preflight_first.json。该工件未转码，未冒称原审核日志；可执行准备脚本及hash回执仍保留。此项仅为开发打包更正，不改变产品源码或测试结论。
