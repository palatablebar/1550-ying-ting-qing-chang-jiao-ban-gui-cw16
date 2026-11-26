# 影厅清场交班轨验证目录

AI/ML · 传统ML · 中型

修改业务链路时先检查受影响模块的测试，再运行整套 `pytest`。回归记录须能够定位到具体单据或计算值。

## 功能模块

| 编号 | 功能 | 核对内容 | 核心文件 | 独立测试 |
|---|---|---|---|---|
| M1 | 场次交接 | 单据版次与隔离 | `src/cinemaready/show_handoffs/service.py` | `tests/test_show_handoffs.py` |
| M2 | 影厅日程 | 截止日和成熟标签 | `src/cinemaready/turnover_calendar/service.py` | `tests/test_turnover_calendar.py` |
| M3 | 清理因素 | 原始数据到特征 | `src/cinemaready/hall_signature/service.py` | `tests/test_hall_signature.py` |
| M4 | 耗时滚动 | 训练及可重复推断 | `src/cinemaready/cleanup_trend/service.py` | `tests/test_cleanup_trend.py` |
| M5 | 窗口复算 | 回放误差及可信区间 | `src/cinemaready/slot_backcheck/service.py` | `tests/test_slot_backcheck.py` |
| M6 | 排片分组 | 差异定位和外推审查 | `src/cinemaready/programming_mix/service.py` | `tests/test_programming_mix.py` |
| M7 | 清场计划 | 硬规则与额度分配 | `src/cinemaready/usher_windows/service.py` | `tests/test_usher_windows.py` |
| M8 | 开厅交接 | 单据及额度证据 | `src/cinemaready/hall_handover/service.py` | `tests/test_hall_handover.py` |
| M9 | 补救排窗 | 赶不上开门场次的措施重算与签发守恒 | `src/cinemaready/remedial_windows/service.py` | `tests/test_remedial_windows.py` |

## 深度登记

| 编号 | 边界 | 判断 | 处理位置 | 测试定位 |
|---|---|---|---|---|
| TRAP-14 | 同版不同读数 | 两条都隔离，换序结论一致 | `src/cinemaready/show_handoffs/service.py` | `tests/test_show_handoffs.py::test_conflicting_same_version_is_order_independent` |
| TRAP-19 | 多个规则或外推标记重叠 | 硬约束优先，保留全部命中码 | `src/cinemaready/usher_windows/service.py` | `tests/test_usher_windows.py::test_hard_rule_precedes_outside_reference` |
| TRAP-23 | 标签落在窗口的终点 | 终点进入隔离段，窗口为半开区间 | `src/cinemaready/turnover_calendar/service.py` | `tests/test_turnover_calendar.py::test_half_open_days` |
| TRAP-32 | 大偏移细方差与常数列 | 中心化后累加，常数列尺度为一 | `src/cinemaready/hall_signature/service.py` | `tests/test_hall_signature.py::test_cancellation_safe_scaling` |
| TRAP-42 | 拟合窗口后才回传结果 | 依标签成熟时间屏蔽，未来数据不参与拟合 | `src/cinemaready/turnover_calendar/service.py` | `tests/test_turnover_calendar.py::test_mature_label_cannot_cross_partition` |
| TRAP-43 | 回放没有成熟记录 | 记录未定义状态，避免以零误差替代 | `src/cinemaready/slot_backcheck/service.py` | `tests/test_slot_backcheck.py::test_no_outcome_gets_undefined_metrics` |
| TRAP-44 | 校准样本不足 | 分派前转人工判读并保留原因 | `src/cinemaready/slot_backcheck/service.py` | `tests/test_slot_backcheck.py::test_empty_calibration_requires_review` |
| TRAP-53 | 单条推断与混批 | 复用冻结参数，各条估计完全一致 | `src/cinemaready/cleanup_trend/service.py` | `tests/test_cleanup_trend.py::test_input_batch_invariance` |
| TRAP-54 | 特征版本与模型不配对 | 拒绝继续推断并要求重拟合 | `src/cinemaready/cleanup_trend/service.py` | `tests/test_cleanup_trend.py::test_mismatched_model_input_version_fails` |
| TRAP-61 | 补救措施改动缺测读数 | 方案不签发并保留缺测原因，措施只能改实测字段 | `src/cinemaready/remedial_windows/options.py` | `tests/test_remedial_windows.py::test_missing_reading_is_never_used_as_a_remedial_change` |
| TRAP-62 | 估计上界留不出开门验收 | 准时方案拒签，先试准时层再退延后层，都不行留待协调 | `src/cinemaready/remedial_windows/service.py` | `tests/test_remedial_windows.py::test_upper_bound_acceptance_gate_rejects_on_time_claim` |
| TRAP-63 | 补救工位与常规分派余额不一致 | 同批重算，补救占用与剩余工位守恒，按措施/开门时刻/工位对账 | `src/cinemaready/remedial_windows/evidence.py` | `tests/test_remedial_windows.py::test_ledger_and_export_reconcile_by_measure_door_and_station` |
