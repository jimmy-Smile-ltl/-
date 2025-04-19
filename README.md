# 骑手排班思路 #

## 1. 确定每天需要的骑手数量与结构 ##

理念：根据一周的场景得到订单，合理分配骑手，这一阶段是分组进行的，不关注骑手个人，今天办法是首先更具订单数量确定总的骑手数量， 至于骑手结构，是在一个区间值内，用线性规划求最优的结构，高kpi：中kpi：低kpi的占比。最大化目标是  订单/运力      就是平均运送一单的骑手数量最大化

### 1.1 天气确定 ###

衡量天气优劣的方法通过以下公式综合计算天气评分（Weather Score），该评分范围为 $0$ 到 $100$，值越高表示天气条件越优。

#### *1.1.1. 计算公式**

##### **1. 总评分公式**

$\text{Weather Score} = w_{\text{weather}} \cdot S_{\text{weather}} + w_{\text{temperature}} \cdot S_{\text{temperature}} + w_{\text{precipitation}} \cdot S_{\text{precipitation}} + w_{\text{humidity}} \cdot S_{\text{humidity}} + w_{\text{wind}} \cdot S_{\text{wind}}$

其中：

- $w_{\text{weather}}, w_{\text{temperature}}, w_{\text{precipitation}}, w_{\text{humidity}}, w_{\text{wind}}$：各指标的权重，总和为 $1$。
- $S_{\text{weather}}, S_{\text{temperature}}, S_{\text{precipitation}}, S_{\text{humidity}}, S_{\text{wind}}$：各指标的评分，范围为 $[0, 1]$。

##### **2. 各指标评分公式**

- **正常天气**：

  - 温度、湿度、风速在舒适范围内。
  - 无强降水、强风、极端天气现象。
  - 温度：$T_{\text{ideal}}$ = [18, 26]。
  - 湿度：$H_{\text{ideal}}$ = [40, 60]。
  - 最大理想风速：$W_{\text{max}} = 20$ km/h。

- **恶劣天气**：

  - 出现对人体健康和出行安全造成影响的天气条件，如：
    - 高风速（> 20 km/h）。
    - 高降水量（> 10 mm）。
    - 极端温度（低于 0°C 或高于 35°C）。
    - 高湿度（> 80%）或低湿度（< 20%）。
    - 特定天气现象（如暴雨、大雪、沙尘）。

  ##### **（1）天气现象评分** #####

  根据天气情况（如晴、多云、小雨等）映射评分：

  $S_{\text{weather}} = f_{\text{weather}}(\text{text-day})$

  其中：

  - $f_{\text{weather}}$ 是一个映射函数，具体评分由天气描述的优劣程度决定。

  ##### **（2）温度评分** #####

  基于理想温度范围（$T_{\text{ideal}} = [T_{\text{low}}, T_{\text{high}}]$）计算：

  $S_{\text{temperature}} = \max\left(0, 1 - \frac{|T_{\text{avg}} - T_{\text{ideal-avg}}|}{10}\right)$

  其中：

  - $T_{\text{avg}} = \frac{T_{\text{high}} + T_{\text{low}}}{2}$：日均温度。
  - $T_{\text{idealavg}} = \frac{T_{\text{low}} + T_{\text{high}}}{2}$：理想日均温度。

  ##### **（3）降水评分** #####

  根据降水量和降水概率计算：

  $S_{\text{precipitation}} = \max\left(0, 1 - \left(\text{Rainfall} + \frac{\text{Precip}}{100}\right)\right)$

  其中：

  - $\text{Rainfall}$：降水量（单位：mm）。
  - $\text{Precip}$：降水概率（单位：%）。

  ##### **（4）湿度评分** #####

  基于理想湿度范围（$H_{\text{ideal}} = [H_{\text{low}}, H_{\text{high}}]$）计算：

  $S_{\text{humidity}} = \max\left(0, 1 - \frac{|H - H_{\text{ideal-avg}}|}{50}\right)$

  其中：

  - $H$：实际湿度（单位：%）。
  - $H_{\text{ideal-avg}} = \frac{H_{\text{low}} + H_{\text{high}}}{2}$：理想平均湿度。

  ##### **（5）风速评分** #####

  基于最大理想风速（$W_{\text{max}}$）计算：

  $S_{\text{wind}} = \max\left(0, 1 - \frac{\max(0, W - W_{\text{max}})}{W_{\text{max}}}\right)$

  其中：

  - $W$：实际风速（单位：km/h）。
  - $W_{\text{max}}$：最大理想风速。

##### **3. 参数说明** 

1. **权重示例**
   - $w_{\text{weather}} = 0.3, w_{\text{temperature}} = 0.25, w_{\text{precipitation}} = 0.2, w_{\text{humidity}} = 0.15, w_{\text{wind}} = 0.1$。

#### 1.1.2 **指数分类依据** ####

1. **指数阈值**：
   - **正常**：指数 >= 70。
   - **恶劣**：指数 < 70。
2. **分类解释**：
   - **正常天气**：指数较高，表明天气舒适，对日常生活和出行影响小。
   - **恶劣天气**：指数较低，表明存在不利因素（如降水、强风等），需要注意防护。

#### **1.1.3天气数据来源（只有14天试用期）**：心知天气   ####

`https://seniverse.yuque.com/hyper_data/api_v3/sl6gvt`

```json

    "daily": [{                          //返回指定days天数的结果
      "date": "2015-09-20",              //日期（该城市的本地时间）
      "text_day": "多云",                //白天天气现象文字
      "code_day": "4",                  //白天天气现象代码
      "text_night": "晴",               //晚间天气现象文字
      "code_night": "0",                //晚间天气现象代码
      "high": "26",                     //当天最高温度
      "low": "17",                      //当天最低温度
      "precip": "0",                    //降水概率，范围0~1，单位百分比（目前仅支持国内城市）
      "wind_direction": "",             //风向文字
      "wind_direction_degree": "255",   //风向角度，范围0~360
      "wind_speed": "9.66",             //风速，单位km/h（当unit=c时）、mph（当unit=f时）
      "wind_scale": "",                 //风力等级
      "rainfall": "0.0",                //降水量，单位mm（目前仅支持国内城市）
      "humidity": "76"                  //相对湿度，0~100，单位为百分比
    }
}
```

#### **1.1.4 计算代码** ####

```python
#有点多 省略
```

### 1.2  假日确定 ###

```python
import holidays
def is_holiday(self,date):
    """判断是否节假日"""
    cn_holidays = holidays.China()
    return date in cn_holidays
```

### 1.3 周末确定 ###

```python
def is_weekend(self, date):
    """判断是否周末"""
    return date.weekday() >= 5
```

### 1.4 订单数确定 ###

五大场景：

 不同场景骑手结构 单量越大，高kpi越多  总的骑手结构：高kpi：中kpi：低kpi=0.3:0.4:0.3
- 正常天气+工作日 ：高kpi：中kpi：低kpi=0.20:0.4:0.40
- 恶劣天气+工作日 ：高kpi：中kpi：低kpi=0.25:0.4:0.35
- 正常天气+周末 ：     高kpi：中kpi：低kpi=0.30:0.4:0.30
- 恶劣天气+周末 ：      高kpi：中kpi：低kpi=0.35:0.4:0.25
- 节假日：                      高kpi：中kpi：低kpi=0.40:0.4:0.20

```python
scenario_params ={
            'festival&holiday': {'order_factor': 1.30, 'kpi_mix': [0.4, 0.4, 0.2]},
            'normal_weekday': {'order_factor': 1.00, 'kpi_mix': [0.2, 0.4, 0.4]},
            'bad_wea_weekday': {'order_factor': 1.05, 'kpi_mix': [0.25, 0.4, 0.35]},
            'normal_weekend': {'order_factor': 1.15, 'kpi_mix': [0.3, 0.4, 0.3]},
            'bad_wea_weekend': {'order_factor': 1.20, 'kpi_mix': [0.35, 0.4, 0.25]}
        }
```

==强调，实际上关注的是该天订单在一周的占比，不需要知道每天实际多少订单==

对美团数据的不同场景单量均值统计

正常天气+工作日 ：20000    

恶劣天气+工作日：21350 

正常天气+周末：22837

节假日：26000

推出恶劣天气+周末 约为   240000（1350+2837）

==比值确定为：1：1.05：1.15：1.20：1.3==

![image-20250417222949967](./../实习-2024暑假-无限集数/picMarkdown/image-20250417222949967.png)

### 1.5 确定骑手运力 ###

![image-20250417225211353](./../实习-2024暑假-无限集数/picMarkdown/image-20250417225211353.png)

==定为 15：25：40 及 3 ：5 ：8==

### 1.6  确定骑手排班偏好 ###

实际上，更合适的让骑手自己选择排序，但是现在不行，就根据年龄等，用代码生成了一份

**偏好值范围**：

- **1**：不喜欢该时段。
- **2**：可以接受该时段。
- **3**：非常喜欢该时段。

**生成依据**：

- 根据骑手的个人特征生成偏好，例如：
  - **有孩子**的骑手可能更倾向于选择早班（方便接送孩子）。
  - **年长**的骑手可能不喜欢熬夜，因此夜班偏好值较低。
  - **单身或年轻**的骑手可能更倾向于夜班（时间灵活）。

### 1.7 确定每天所需的骑手数量与结构
#### **1. 问题描述** ####

第一阶段的目标是根据 7 天的订单预测，确定每天需要的骑手总人数以及优秀、良好、一般骑手的比例构成，使得：
1. 每天的理论配送能力与订单需求接近，且各天的理论配送能力与订单需求比值浮动范围较小。
2. 满足一周内骑手总人数的全局分配比例限制。
3. 满足每日优秀、良好、一般骑手的比例限制。

#### **2. 目标函数** ####

目标是最大化 7 天每天的理论配送能力与订单需求比值的和：

$$\text{Maximize: } \sum_{d=1}^{7} \frac{x_{\text{excellent},d} \cdot e_{\text{excellent}} + x_{\text{good},d} \cdot e_{\text{good}} + x_{\text{average},d} \cdot e_{\text{average}}}{\text{订单量}_d}$$

其中：

- $x_{\text{excellent},d}, x_{\text{good},d}, x_{\text{average},d}$：第 $d$ 天优秀、良好、一般骑手的数量。
- $e_{\text{excellent}}, e_{\text{good}}, e_{\text{average}}$：优秀、良好、一般骑手的效率系数（分别为 40、25、15）。
- $\text{订单量}_d$：第 $d$ 天的订单量。

#### **3. 约束条件** ####

##### **（1）全局约束** #####

一周内每种类型骑手的总工作天数需满足全局比例限制，一个骑手都只上五天班：

$$\sum_{d=1}^{7} x_{\text{excellent},d} = 5 \cdot \text{优秀骑手总数}$$
	$$\sum_{d=1}^{7} x_{\text{good},d} = 5 \cdot \text{良好骑手总数}$$
	$$\sum_{d=1}^{7} x_{\text{average},d} = 5 \cdot \text{一般骑手总数}$$

##### **（2）每日骑手总人数约束** #####

每天的优秀、良好、一般骑手总人数必须满足当天骑手	需求：

$x_{\text{excellent},d} + x_{\text{good},d} + x_{\text{average},d} = \text{骑手需求}_d$

##### **（3）每日骑手比例约束** #####

每天优秀、良好、一般骑手的比例应在合理范围内波动：

$$0.2 \cdot \text{骑手需求}_d \leq x_{\text{excellent},d} \leq 0.4 \cdot \text{骑手需求}_d$$
	$$0.35 \cdot \text{骑手需求}_d \leq x_{\text{good},d} \leq 0.45 \cdot \text{骑手需求}_d$$
	$$0.2 \cdot \text{骑手需求}_d \leq x_{\text{average},d} \leq 0.4 \cdot \text{骑手需求}_d$$

##### **（4）运力充足率约束** #####

每天的理论配送能力与订单需求比值需接近全局基准比值，这个约束很重要，保障的是每天的运力充足率差不多，都在基准值附近，根据订单数吧运力均匀分布到每一天，：

$$\text{基准比值} = \frac{\text{一周总配送能力}}{\text{一周总订单量}}$$
	$$\text{基准比值} - 0.01 \leq \frac{x_{\text{excellent},d} \cdot e_{\text{excellent}} + x_{\text{good},d} \cdot e_{\text{good}} + x_{\text{average},d} \cdot e_{\text{average}}}{\text{订单量}_d}$$

#### **4. 理论依据** ####

1. **线性规划优化**
    在约束条件下最大化目标函数，确保每天的配送能力与订单需求比值接近，同时平衡一周内骑手的工作负担。
2. **资源分配原则**
    满足每天订单量的同时，合理调整骑手结构比例，优化整体运力。

## 2.确定每天具体有哪些骑手上班 ##

> 思路： 最优化目标是准时单量，第一阶段的得出结构与比例是基于骑手组的，本阶段进一步细分，分人进行，关注核心kpi，准时单量，最大化目标是准时单量最大化，第一阶段的骑手解构是约束条件

### 2.1 计算每个骑手平均准时率 ###

这个准时率理论上也会随着技术/经验的增加而提升的呀

12月骑手的总准时单/总单 

### 2.2 骑手的运力 

稍显复杂，时间不一样了，骑手在20个月工作经验之前，随着工作经验的增加，技术更加成熟，操作更加熟练，能完成更多单量，这一点，得到了数据支撑。

###  2.3 第二阶段如何确定每天具体有哪些骑手上班 ###
#### **1. 问题描述** ####
第二阶段的目标是在第一阶段确定的每天骑手总人数及优秀、良好、一般骑手构成的基础上，进一步分配具体哪些骑手上班，以最大化订单准时完成量，满足以下要求：
1. 每天的骑手总人数及构成比例严格符合第一阶段的分配结果。
2. 每个骑手一周的工作天数不超过 5 天。
3. 每个骑手在同一天只能上班一次（即不重复分配）。
4. 优化结果最大化订单的准时完成量，考虑不同骑手的效率和实际需求。
#### **2. 目标函数** ####
目标是最大化每天的订单准时完成量，具体定义为：
$\text{Maximize: } \sum_{d=1}^{7} \left( x_{\text{excellent},d} \cdot e_{\text{excellent}} + x_{\text{good},d} \cdot e_{\text{good}} + x_{\text{average},d} \cdot e_{\text{average}} \right)$
其中：
- $x_{\text{excellent},d}, x_{\text{good},d}, x_{\text{average},d}$：第 $d$ 天实际分配的优秀、良好、一般骑手的数量。
- $e_{\text{excellent}}, e_{\text{good}}, e_{\text{average}}$：优秀、良好、一般骑手的效率系数（分别为 40、25、15）。
- $d \in {1, 2, \dots, 7}$：一周内的天数。
#### **3. 约束条件** ####
##### **（1）每日骑手总人数约束** #####
每天的骑手总人数及构成需严格符合第一阶段的分配结果：
$\sum_{r \in \text{Riders}} x_{r,d} = \text{骑手需求}_d$
对于优秀、良好、一般骑手分别满足：
$$\sum_{r \in \text{Excellent-Riders}} x_{r,d} = \text{优秀骑手数量}_d$$
$$\sum_{r \in \text{Good-Riders}} x_{r,d} = \text{良好骑手数量}_d$$
$$\sum_{r \in \text{Average-Riders}} x_{r,d} = \text{一般骑手数量}_d$$
##### **（2）骑手工作天数约束** #####
每个骑手一周的工作天数不超过 5 天：
$\sum_{d=1}^{7} x_{r,d} \leq 5 \quad \forall r \in \text{Riders}$
##### **（3）骑手当天唯一工作约束** #####
每个骑手在同一天只能上班一次：
$x_{r,d} \in \{0, 1\} \quad \forall r \in \text{Riders}, \forall d \in \{1, 2, \dots, 7\}$
##### **（4）运力与订单需求匹配** #####
每天分配的骑手总运力需至少达到订单需求：
$x_{\text{excellent},d} \cdot e_{\text{excellent}} + x_{\text{good},d} \cdot e_{\text{good}} + x_{\text{average},d} \cdot e_{\text{average}} \geq \text{订单量}_d$
#### **4. 理论依据** ####
1. **线性规划优化**
    通过约束条件确保每天具体分配的骑手满足总人数及结构要求，同时最大化订单准时完成量。
2. **效率优化原则**
    优先分配效率高的骑手（优秀骑手）以提高整体准时单量，同时平衡良好和一般骑手的分配。
3. **公平性原则**
    每个骑手的工作负担受限于一周最多 5 天，确保分配的公平性。
#### **5. 总结** ####
第二阶段通过线性规划的资源分配优化方法，确定了每天具体上班的骑手名单，使得：
1. 每天的骑手人数及构成严格符合第一阶段的分配结果。
2. 优化了订单准时完成量，提升了整体配送效率。
3. 确保了骑手工作负担的公平性和合理性。

## 3.确定每天骑手上班的时间段 ##

#### **1. 问题描述**

==午饭、晚饭两个高峰，所有人都要上班==

第二阶段的目标是在第一阶段确定的每天骑手数量和结构基础上，合理分配骑手到具体的工作时段（早茶、下午茶、夜宵），并考虑骑手的个人偏好，最大化骑手满意度，同时满足如下要求：

1. 午饭和晚饭两个高峰期是固定工作时段，所有骑手都需覆盖，另外每个骑手每天还需选择一个时段工作。
2. 早茶、下午茶、夜宵三个时段可根据骑手的偏好灵活分配，但每个时段的骑手人数符合比例要求（如早、中、晚的比例约束为 $1:1:1$，允许误差不超过 20%）。
3. 优化分配使骑手的偏好得到最大化，同时满足每个时段的基本运力需求。

------

#### **2. 目标函数** ####

目标是最大化一周内所有骑手的偏好匹配总分：

$\text{Maximize: } \sum_{r \in \text{Riders}} \sum_{d=1}^{7} \sum_{t \in \text{Time-Slots}} x_{r,d,t} \cdot \text{Preference}_{r,t}$

其中：

- $x_{r,d,t}$：二元变量，表示骑手 $r$ 在第 $d$ 天的时段 $t$ 是否工作（1 为工作，0 为不工作）。
- $\text{Preference}_{r,t}$：骑手 $r$ 对时段 $t$ 的偏好分值（1-3 分，3 表示非常喜欢）。
- $\text{Time-Slots}$：包括早茶、下午茶、夜宵三个灵活时段。

------

#### **3. 约束条件** ####

##### **（1）午饭和晚饭时段全覆盖** #####

所有骑手必须在午饭和晚饭两个高峰期工作：

$\forall r \in \text{Riders}, \forall d \in \{1, 2, \dots, 7\}, \quad x_{r,d,\text{lunch}} = 1, \quad x_{r,d,\text{dinner}} = 1$

##### **（2）骑手每日最多选择一个灵活时段** #####

每个骑手每天只能选择一个灵活时段（早茶、下午茶、夜宵）：

$\sum_{t \in \{\text{morning}, \text{afternoon}, \text{night}\}} x_{r,d,t} \leq 1 \quad \forall r \in \text{Riders}, \forall d \in \{1, 2, \dots, 7\}$

##### **（3）每个时段的骑手人数约束** #####

目标是控制每天早茶、下午茶、夜宵三个灵活时段骑手的分配比例，使其接近 $1:1:1$，并确保每个时段的骑手人数相差不超过 20%。第三阶段约束方程解释

**时段人数计算** 

每个时段的骑手人数可以表示为：

$$\text{Morning-Count}_d = \sum_{r \in \text{Riders}} x_{r,d,\text{morning}}$$
	$$\text{Afternoon-Count}_d = \sum_{r \in \text{Riders}} x_{r,d,\text{afternoon}}$$
	$$\text{Night-Count}_d = \sum_{r \in \text{Riders}} x_{r,d,\text{night}}$$

- $\text{Morning-Count}_d$：第 $d$ 天早茶时段的骑手人数。
- $\text{Afternoon-Count}_d$：第 $d$ 天下午茶时段的骑手人数。
- $\text{Night-Count}_d$：第 $d$ 天夜宵时段的骑手人数。

##

**早茶与下午茶时段人数比例约束**

要求早茶时段人数与下午茶时段人数相差不超过 20%，即满足：

$0.8 \cdot \text{Afternoon-Count}_d \leq \text{Morning-Count}_d \leq 1.2 \cdot \text{Afternoon-Count}_d$

**（2）早茶与夜宵时段人数比例约束**

要求早茶时段人数与夜宵时段人数相差不超过 20%，即满足：

$0.8 \cdot \text{Night-Count}_d \leq \text{Morning-Count}_d \leq 1.2 \cdot \text{Night-Count}_d$

**（3）下午茶与夜宵时段人数比例约束** 

要求下午茶时段人数与夜宵时段人数相差不超过 20%，即满足：

$0.8 \cdot \text{Night-Count}_d \leq \text{Afternoon-Count}_d \leq 1.2 \cdot \text{Night-Count}_d$

#### **4. 理论依据** 

1. **比例约束的意义**
    通过控制三个灵活时段的骑手人数比例，确保每个时段的运力需求得到均衡分配，避免某些时段骑手过多或过少的情况。
2. **20% 的浮动范围**
    允许一定的灵活性，使得骑手分配更具实际操作性，同时不偏离目标比例 $1:1:1$。

#### **5. 总结** ####

第三阶段通过优化灵活时段的骑手分配：

1. 固定覆盖了午饭和晚饭高峰期的工作需求。
2. 根据骑手偏好最大化了整体满意度。
3. 在满足最低运力需求的前提下，实现了骑手意愿与运力需求的有效平衡。
