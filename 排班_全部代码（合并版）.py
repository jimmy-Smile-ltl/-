# -*- coding: utf-8 -*-
# @Time    : 2025/4/15 21:17
# @Author  : Jimmy Smile
# @Project : 选题一
# @File    : 排班_智能体版.py
# @Software: PyCharm
"""
# 基本代码在
#  1.排班_线性规划_求总数与结构.py
#  2.排班_考虑骑手偏好.py

本部分主要是在智能体内部读取 数据库对数据库数据的加工处理
天气的获取也需要完善，暂定代码获取日期
"""

import pulp
import random
import json5
import pandas as pd
import holidays
import requests
from collections import Counter
import time
class RiderScheduling:
    def __init__(self):
        # 基本参数
        self.location = "beijing"
        self.start = self.adjust_start() #  下周一 距离今天
        self.riders,self.high_riders,  self.medium_riders, self.low_riders = self.get_riders()
        self.num_riders = len(self.riders)
        self.num_high_riders = len(self.high_riders)
        self.num_medium_riders = len(self.medium_riders)
        self.num_low_riders = len(self.low_riders)
        self.days = 7 # 7天 天气预报获取7天
        self.time_slots = ["morning", "afternoon", "night"] # 第三阶段排班用
        self.base_order = 20000 # 基础订单量 不影响的 关注的是比例
        self.work_days = 5
        self.daily_data = [] # 第一阶段结果
        self.scenarios = [] # 场景
        self.severe_weather_conditions = ["暴雨", "大雪", "沙尘"]

        # 参数配置
        self.scenario_params = {
            'festival&holiday': {'order_factor': 1.30, 'kpi_mix': [0.4, 0.4, 0.2]},
            'normal_weekday': {'order_factor': 1.00, 'kpi_mix': [0.2, 0.4, 0.4]},
            'bad_wea_weekday': {'order_factor': 1.05, 'kpi_mix': [0.25, 0.4, 0.35]},
            'normal_weekend': {'order_factor': 1.15, 'kpi_mix': [0.3, 0.4, 0.3]},
            'bad_wea_weekend': {'order_factor': 1.20, 'kpi_mix': [0.35, 0.4, 0.25]}
        }
        self.rider_class = {
            'high': {'ratio': 0.3, 'efficiency': 40},
            'medium': {'ratio': 0.4, 'efficiency': 25},
            'low': {'ratio': 0.3, 'efficiency': 15}
        }
    def get_riders(self):
        """
        从数据库获取骑手数据
        """
        # 读取骑手数据
        df = pd.read_excel("排班_骑手信息_准时_偏好.xlsx")
        # 偏好列 str 转 dict
        df["preference"] = df["preference"].apply(lambda x: eval(x))
        #注册时间 转化为str
        df["regist_date"] = pd.to_datetime(df["regist_date"]).dt.strftime("%Y-%m-%d")
        rider_data = df.to_dict(orient="records")
        # 优秀骑手数
        high_riders = df[df["绩效类别"] == "优秀骑手"]
        # 正常骑手数
        medium_riders = df[df["绩效类别"] == "正常骑手"]
        # 一般骑手数
        low_riders = df[df["绩效类别"] == "一般骑手"]
        high_data = high_riders.to_dict(orient="records")
        medium_data = medium_riders.to_dict(orient="records")
        low_data = low_riders.to_dict(orient="records")

        return rider_data, high_data, medium_data, low_data

    def get_results(self):
        """
        获取第一阶段的结果
        """
        return self.daily_data

    def is_holiday(self, date):
        """
        判断指定日期是否为 2025 年的节假日。
        """
        if date in holidays.China():
            return True
        return False

    def is_weekend(self, date):
        """判断是否周末"""
        return date.weekday() >= 5

    def adjust_start(self):
        # 从下周一开始
        today = pd.Timestamp.today()
        next_monday = today + pd.DateOffset(days=(7 - today.weekday()))
        start = (next_monday - today).days
        return start

    def get_weather_data(self):
        """
               获取指定城市的天气数据。
               """
        weather_api = "https://api.seniverse.com/v3/weather/daily.json"
        params = {
            "key": "S8K5R-PLMcY-OT1R_",  # 替换为你的API密钥
            "location": self.location,
            "language": "zh-Hans",
            "unit": "c",
            "start": self.start,
            "days": self.days
        }

        try:
            response = requests.get(weather_api, params=params)
            response.raise_for_status()
            self.weather_data = response.json()["results"][0]["daily"]
        except requests.exceptions.RequestException as e:
            print(f"请求天气数据失败：{e}")
            self.weather_data = []

    def calculate_weather_score(self):
        """
        计算天气综合评分，范围为 0（非常差）到 100（非常好）。
        """
        if not self.weather_data:
            print("天气数据为空，无法计算评分。")
            return

        # 权重分配
        weights = {
            "weather": 0.3,
            "temperature": 0.25,
            "precipitation": 0.2,
            "humidity": 0.15,
            "wind": 0.1
        }
        ideal_temp_range = (18, 26)
        ideal_humidity_range = (40, 60)
        max_wind_speed = 20

        weather_score_mapping = {
            "晴": 1.0, "多云": 0.8, "阴": 0.6, "小雨": 0.4, "大雨": 0.2, "暴雨": 0.0
        }

        def get_weather_score(text_day):
            return weather_score_mapping.get(text_day, 0.5)

        for day in self.weather_data:
            weather_score = get_weather_score(day.get("text_day", "晴"))
            high = float(day.get("high", 0))
            low = float(day.get("low", 0))
            avg_temp = (high + low) / 2
            temp_score = max(0.0, 1 - abs(avg_temp - sum(ideal_temp_range) / 2) / 10)

            rainfall = float(day.get("rainfall", 0))
            precip = float(day.get("precip", 0))
            precip_score = max(0.0, 1 - (rainfall + precip / 100))

            humidity = float(day.get("humidity", 0))
            humidity_score = max(0.0, 1 - abs(humidity - sum(ideal_humidity_range) / 2) / 50)

            wind_speed = float(day.get("wind_speed", 0))
            wind_score = max(0.0, 1 - max(0, wind_speed - max_wind_speed) / max_wind_speed)

            overall_score = (
                    weights["weather"] * weather_score +
                    weights["temperature"] * temp_score +
                    weights["precipitation"] * precip_score +
                    weights["humidity"] * humidity_score +
                    weights["wind"] * wind_score
            )
            day["score"] = round(overall_score * 100, 2)

    def classify_weather(self):
        """
        根据评分分类天气为正常或恶劣，并解释理由。
        """
        if not self.weather_data:
            print("天气数据为空，无法分类。")
            return None

        for day in self.weather_data:
            # 特定天气现象直接归为恶劣天气
            if day.get("text_day") in self.severe_weather_conditions:
                day["classification"] = "恶劣"
                day["reason"] = f"特定天气现象：{day['text_day']}。"
                continue

            score = day.get("score", 0)
            if score >= 70:
                day["classification"] = "正常"
                day["reason"] = "天气舒适，无显著不利因素。"
            else:
                day["classification"] = "恶劣"
                reasons = []
                if float(day.get("wind_speed", 0)) > 20:
                    reasons.append("风速较大")
                if float(day.get("precip", 0)) > 50 or float(day.get("rainfall", 0)) > 10:
                    reasons.append("降水量较大")
                if float(day.get("high", 0)) > 35 or float(day.get("low", 0)) < 0:
                    reasons.append("极端温度")
                if float(day.get("humidity", 0)) > 80 or float(day.get("humidity", 0)) < 20:
                    reasons.append("湿度不适宜")
                day["reason"] = "，".join(reasons) if reasons else "存在不利天气条件。"

        for day in self.weather_data:
            print(
                f"日期: {day['date']}, 综合评分: {day.get('score', '无')}, 分类: {day.get('classification')}, 原因: {day.get('reason')}")
            print(day)

    def is_wea_good(self, date):
        # 暂时随机 返回True False
        for day in self.weather_data:
            if day["date"] == date.strftime("%Y-%m-%d"):
                if day.get("classification") == "正常":
                    return True
                elif day.get("classification") == "恶劣":
                    return False
                else:
                    raise ValueError(f"天气分类错误: {day.get('classification')}")
        else:
            raise ValueError(f"日期 {date} 不在天气数据中。")


    def generate_scenarios(self):
        """
        生成分配场景
        """
        date_start = pd.Timestamp.today() + pd.DateOffset(days=self.start)
        self.get_weather_data()
        self.calculate_weather_score()
        self.classify_weather()
        for day in range(self.days):
            date = date_start + pd.DateOffset(days=day)
            if self.is_holiday(date):
                # 节假日
                scenario = 'festival&holiday'
            elif self.is_weekend(date):
                # 周末
                if self.is_wea_good(date):
                    scenario = 'normal_weekend'
                else:
                    scenario = 'bad_wea_weekend'
            else:
                # 工作日
                if self.is_wea_good(date):
                    scenario = 'normal_weekday'
                else:
                    scenario = 'bad_wea_weekday'

            self.scenarios.append(scenario)

    def first_stage(self):
        """
        第一阶段：分配每天的骑手数量与结构。
        """
        # 创建线性规划问题
        problem = pulp.LpProblem(f"Rider_Scheduling_First_Stage", pulp.LpMaximize)
        # 决策变量
        x_high = pulp.LpVariable.dicts(
            "x_high",
            (day for day in range(self.days)),
            lowBound=0.2 * self.num_high_riders,
            upBound=self.num_high_riders,
            cat="Integer"
        )
        x_medium = pulp.LpVariable.dicts(
            "x_medium",
            (day for day in range(self.days)),
            lowBound=0.2 * self.num_medium_riders,
            upBound=self.num_medium_riders,
            cat="Integer"
        )
        x_low = pulp.LpVariable.dicts(
            "x_low",
            (day for day in range(self.days)),
            lowBound=0.2 * self.num_low_riders,
            upBound=self.num_low_riders,
            cat="Integer"
        )
        #
        # 全局约束 每组骑手 每个骑手上五天班
        problem += pulp.lpSum([x_high[day] for day in range(self.days) ]) == self.work_days * self.num_high_riders
        problem += pulp.lpSum([x_medium[day] for day in range(self.days) ]) ==  self.work_days * self.num_medium_riders
        problem += pulp.lpSum([x_low[day] for day in range(self.days)  ]) ==  self.work_days * self.num_low_riders

        # 逐日约束
        orders_days = []
        all_orders = sum([self.scenario_params[scenario]['order_factor'] for scenario in self.scenarios])
        # 总订单
        sum_orders = sum([self.base_order * self.scenario_params[scenario]['order_factor'] for scenario in self.scenarios])
        # 这个是总的运力
        sum_efficiency = (self.rider_class["high"]["efficiency"] * self.num_high_riders * self.work_days
                          + self.rider_class["medium"]["efficiency"] * self.num_medium_riders * self.work_days
                          +self.rider_class["low"]["efficiency"] * self.num_low_riders *  self.work_days)
        # 比值，总的比例，每天的比例应该在这个基础上浮动 95%-105%
        base_ratio = sum_efficiency / sum_orders
        for day, scenario in enumerate(self.scenarios):
            params = self.scenario_params[scenario]
            order_factor = params['order_factor']
            kpi_mix = params['kpi_mix']
            orders = self.base_order * order_factor
            orders_days.append(orders)
            # 能完成总单量
            efficiency = (x_high[day] * self.rider_class["high"]["efficiency"]
                        + x_medium[day] * self.rider_class["medium"]["efficiency"]
                        +  x_low[day] * self.rider_class["low"]["efficiency"]
                        ) / orders
            problem += efficiency >= base_ratio - 0.01
            rider_should = x_high[day] + x_medium[day] + x_low[day]
            # 每天的总骑手数
            problem += x_high[day] + x_medium[day] + x_low[day] == rider_should
            # 正常骑手 0.3 - 0.5 之间
            problem += x_medium[day] >= 0.38 * rider_should
            problem += x_medium[day] <= 0.42 * rider_should
            # 低 KPI 骑手 0.3 - 0.5 之间
            problem += x_low[day] >= 0.2 * rider_should
            problem += x_low[day] <= 0.4 * rider_should
            # 高 KPI 骑手 0.2 - 0.4 之间
            problem += x_high[day] >= 0.2 * rider_should
            problem += x_high[day] <= 0.4 * rider_should

            # 调整结构
            # 判断是否需要减少高 KPI 骑手 但是这个都只能控制比值， 绝对数不能控制
            # if kpi_mix[0] <  self.rider_class["high"]["ratio"]:
            #     # 这是单子少的一天，不加限制，存在高kpi 会倾向最大值的趋势
            #     # 期待值小于整体 减少高 KPI 骑手比例
            #     problem += x_high[day] <=  self.rider_class["high"]["ratio"] * rider_should
            #     # problem += x_low[day] >=  self.rider_class["medium"]["ratio"] * rider_should
            #     problem += x_high[day] >= kpi_mix[0] * rider_should
            #     problem += x_low[day] <=  kpi_mix[2] * rider_should
            # else:  # 增加高 KPI 骑手的情况
            #     problem += x_high[day] >=  self.rider_class["high"]["ratio"] * rider_should
            #     problem += x_low[day] <=  self.rider_class["medium"]["ratio"] * rider_should
            #     # problem += x_high[day] <= kpi_mix[0] * rider_should
            #     # problem += x_low[day] >=  kpi_mix[2] * rider_should

        problem += pulp.lpSum([
            (
                    x_high[day] * self.rider_class["high"]["efficiency"] +
                    x_medium[day] * self.rider_class["medium"]["efficiency"] +
                    x_low[day] * self.rider_class["low"]["efficiency"]
            ) / orders_days[day]
            for day in range(self.days)
        ])

        problem.solve(pulp.PULP_CBC_CMD(timeLimit=10, msg=False))
        while pulp.LpStatus[problem.status] != "Optimal":
            problem.solve(pulp.PULP_CBC_CMD(timeLimit=10, msg=False))
            print("没有找到最优解，重新求解")
            time.sleep(5)
            # raise TypeError("没有找到最优解")

        for day, scenario in enumerate(self.scenarios):
            # 获取当前场景参数
            params = self.scenario_params[scenario]
            order_factor = params['order_factor']
            efficiency = (x_high[day] * self.rider_class["high"]["efficiency"] +
                        x_medium[day] * self.rider_class["medium"]["efficiency"] +
                         x_low[day] * self.rider_class["low"]["efficiency"]
                         ) / orders_days[day]
            # 保存结果
            self.daily_data.append({
                'day': day + 1,
                "date_str": (pd.Timestamp.today() + pd.DateOffset(days=day+self.start)).strftime("%Y-%m-%d"),
                'scenario': scenario,
                "weather_data": self.weather_data[day],
                'orders': int(self.base_order * order_factor),
                "riders_sum": int(pulp.value(x_high[day])) + int(pulp.value(x_medium[day])) + int(
                    pulp.value(x_low[day])),
                'high_kpi': int(pulp.value(x_high[day])),
                'medium_kpi': int(pulp.value(x_medium[day])),
                'low_kpi': int(pulp.value(x_low[day])),
                "efficiency": pulp.value(efficiency),
            })

        def show_statistic(results_para: list):
            # 输出结果
            print(f"{'Day':<5} {'Scenario':<20} {'Orders':<10} "
                  f"{'Riders_sum':<20} {'High KPI':<10} {'Medium KPI':<10} {'Low KPI':<10}"
                  f" {'high_ratio':<10}  {'medium_ratio':<10} {'low_ratio':<10} {'efficiency':<10}" )
            for res in results_para:
                print(f"{res['day']:<5} {res['scenario']:<20} {res['orders']:<10.0f} "
                      f" {res['low_kpi'] + res['medium_kpi'] + res['high_kpi']:<20} "
                      f"{res['high_kpi']:<10} {res['medium_kpi']:<10} {res['low_kpi']:<10}"
                      f"{res['high_kpi'] / res['riders_sum']:<10.2%} "
                      f"{res['medium_kpi'] / res['riders_sum']:<10.2%} "
                      f"{res['low_kpi'] / res['riders_sum']:<10.2%} "
                      f"{res['efficiency']:<10.2%}")
            # 这个结果输出成List<Dict>
            # 结果的描述性统计 ，分别求和每天的总数.high_kpi，medium_kpi，low_kpi，
            print("总骑手数_应该：", self.num_riders * self.work_days,end="\t" )  # 加总偏小，原因是 int 造成的损失
            print("总骑手数_实际：", sum([res['high_kpi'] + res['medium_kpi'] + res['low_kpi'] for res in results_para]))
            print("高kpi骑手数：  计划：", sum([res['high_kpi'] for res in results_para]), "应该:", self.num_high_riders * self.work_days  )
            print("中kpi骑手数：  计划：", sum([res['medium_kpi'] for res in results_para]) , "应该:", self.num_medium_riders * self.work_days)
            print("低kpi骑手数：  计划：", sum([res['low_kpi'] for res in results_para]) , "应该:", self.num_low_riders * self.work_days)
        show_statistic(self.daily_data)
        print("第一阶段完毕")

    def two_stage(self):
        """
        第二阶段：根据第一阶段的结果，确定哪些骑手在哪天上班，最大化目标是准时单量。
        :return:
        """
        x = pulp.LpVariable.dicts(
            "x",
            ((r["rider_id"], d, ) for r in self.riders for d in range(self.days) ),
            cat="Binary"
        )
        # 最大化目标 骑手 运力*准时率 7天加总 最大
        problem = pulp.LpProblem("Rider_Scheduling_Second_Stage", pulp.LpMaximize)
        problem += pulp.lpSum([
            x[r["rider_id"], d] * r["rate_ontime"] * r["cnt_waybill_mean"]
            for r in self.riders for d in range(self.days)
        ])
        # 约束条件 骑手之上5天班
        for r in self.riders:
            problem += pulp.lpSum([x[r["rider_id"], d] for d in range(self.days) ]) == self.work_days
        for d, data in enumerate(self.daily_data):
            # 每天的骑手总数与结构
            total_riders = data['riders_sum']
            high_riders = data['high_kpi']
            medium_riders = data['medium_kpi']
            low_riders = data['low_kpi']

            # 总人数约束 3个时段相加 是该天总人数
            problem += pulp.lpSum(
                [x[r["rider_id"], d] for r in self.riders]) == total_riders

            # # 高 KPI 骑手数量约束
            problem += pulp.lpSum(
                [x[r["rider_id"], d] for r in self.riders if r["绩效类别"] == "优秀骑手"]) == high_riders
            # # 中 KPI 骑手数量约束
            problem += pulp.lpSum(
                [x[r["rider_id"], d] for r in self.riders  if
                 r["绩效类别"] == "正常骑手"]) == medium_riders

            # # 低 KPI 骑手数量约束
            problem += pulp.lpSum(
                [x[r["rider_id"], d] for r in self.riders  if r["绩效类别"] == "一般骑手"]) == low_riders
            #
        problem.solve( pulp.PULP_CBC_CMD(timeLimit=10, msg=False))
        if pulp.LpStatus[problem.status] != "Optimal":
            raise  TypeError("没有找到最优解")
        # 结果解析 把这个结果写入self.daily_data 增加一个属性 riders 下面，哪天要上班的骑手就添加进去
        for d, data in enumerate(self.daily_data):
            date_str = data['date_str']
            if "riders" not in data:
                # 如果没有这个属性，就添加进去
                data["riders"] = []
            for r in self.riders:
                if "work_day" not in r:
                    # 如果没有这个属性，就添加进去
                    r["work_day"] = []
                if pulp.value(x[r["rider_id"], d]) == 1:
                    # 这个骑手在这一天上班
                    r["work_day"].append(date_str)
                    data["riders"].append(r)
                else:
                    # 不上班
                    continue
        # 统计骑手上班天数
        days =[]
        for r in self.riders:
            if "work_day" not in r:
                # 如果没有这个属性，就添加进去
                r["work_day"] = []
            days.append(len(r["work_day"]))
        print("骑手上班天数统计：")
        counter = Counter(days)
        for k, v in counter.items():
            print(f"上班天数 {k} : {v} 个骑手")

    def three_stage(self):
        """
        第二阶段：调整一天内的骑手排班最大化偏好值。
        """
        for d , data in enumerate(self.daily_data):
            date_str = data['date_str']
            today_riders = data['riders']
            problem = pulp.LpProblem(f"Rider_Scheduling_Third_Stage_{d}", pulp.LpMaximize)
            # 决策变量 哪个时段上班
            x = pulp.LpVariable.dicts(
                "x",
                ((r["rider_id"],d, t) for r in today_riders for t in self.time_slots),
                cat="Binary"
            )

            # 只能选择一个时段
            for r in today_riders:
                problem += pulp.lpSum([x[r["rider_id"], d, t] for t in self.time_slots]) == 1

            # # 每天时段分配比例大约在 1:1:1 附近 最大值与最小值 相差不超过 20%
            # # 各时段骑手数量
            morning_count = pulp.lpSum([x[r["rider_id"],d, self.time_slots[0] ] for r in today_riders ])
            afternoon_count = pulp.lpSum([x[r["rider_id"],d, self.time_slots[1] ] for r in today_riders ])
            night_count = pulp.lpSum([x[r["rider_id"],d, self.time_slots[2] ] for r in today_riders ])

            # 确保各时段人数差异不超过 20%
            # 1. 比较 morning 和 afternoon
            problem += morning_count >= 0.8 * afternoon_count
            problem += morning_count <= 1.2 * afternoon_count
            # 2. 比较 morning 和 night
            problem += morning_count >= 0.8 * night_count
            problem += morning_count <= 1.2 * night_count
            # 3. 比较 afternoon 和 night
            problem += afternoon_count >= 0.8 * night_count
            problem += afternoon_count <= 1.2 * night_count

            # 目标函数：最大化骑手偏好值之和
            problem += pulp.lpSum([
                x[r["rider_id"],d, t] * r["preference"][t]
                for r in today_riders for t in self.time_slots
            ])
            problem.solve( pulp.PULP_CBC_CMD(timeLimit=10, msg=False))
            if pulp.LpStatus[problem.status] != "Optimal":
                raise TypeError("没有找到最优解")
            # 结果保存,在riders中增加一个属性，上班的时间段 list<str>
            for r in today_riders:
                if "work_time" not in r:
                    # 如果没有这个属性，就添加进去
                    r["work_time"] = {}
                for t in self.time_slots:
                    if pulp.value(x[r["rider_id"],d, t]) == 1:
                        r["work_time"][date_str] = [t,"peak_dinner","peak_lunch"]

            print(f"{date_str}排班结果：",end=" \t")
            # 统计每天的骑手数量
            morning_count = sum([1 for r in today_riders if "morning" in r["work_time"][date_str] ])
            afternoon_count = sum([1 for r in today_riders if "afternoon" in r["work_time"][date_str] ])
            night_count = sum([1 for r in today_riders if "night" in r["work_time"][date_str]])
            print(f"骑手数量{len(data['riders'])}：早茶：{morning_count}，下午茶：{afternoon_count}，夜宵：{night_count}",)


# 示例运行
scheduler = RiderScheduling()
scheduler.generate_scenarios()
while True:
    try:
        scheduler.first_stage()
        scheduler.two_stage()
        scheduler.three_stage()
        result = scheduler.get_results()
        print(result[0]["riders"][0])
        json5.dump(result, open(f"排班结果_{result[0]['date_str']}_{result[-1]['date_str']}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=4)
    except requests.exceptions.RequestException as e:
        # 报错位置是在第一个 probelm.solve() 哪里 主要是我约束的太死了，每天的配送能力相差控制得非常小
        continue
print("完成")



