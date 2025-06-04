# Amazon Sales Intelligence Dashboard (Power BI Project)

This project presents a comprehensive business intelligence dashboard built using Power BI on Amazon sales data. The goal is to uncover actionable insights that can help optimize revenue, manage discounts, and improve customer satisfaction through data-driven decisions.

---

# Objective

To design an interactive and impactful dashboard using Amazon product sales and review data, helping business stakeholders:
- Identify top-performing product categories
- Assess discount efficiency
- Analyze customer feedback
- Compare ratings and sales across categories

---

# Dataset

**File:** `amazon_sales.xlsx`  
**Source:** https://www.kaggle.com/datasets/karkavelrajaj/amazon-sales-dataset

It includes:
- Product details (name, ID, category)
- Pricing info (actual & discounted price, discount %)
- Ratings and reviews
- Product links and image URLs

---

# Key Business Questions Answered

- **Which categories are driving the most revenue?**
- **Are discount strategies aligned with revenue generation?**
- **What do customers frequently say in reviews?**
- **Which individual products generate the highest revenue?**
- **How does each category perform in terms of revenue vs. customer satisfaction?**

---

# Steps:

### 1. Data Loading & Cleaning (Power Query Editor)
- Fixed data types for numerical fields
- Split category column into `Main Category` and `Sub Categories`
- Removed null values and cleaned review text for Word Cloud

### 2. Data Modeling
- Generally, create relationships if needed (in this case, one table was sufficient)
  
### Calculated columns created
- discount = [actual_price] - [discounted_price] 
- discountpercent = (([actual_price] - [discounted_price]) / [actual_price]) * 100

### DAX Measures Created
- Total Revenue  = SUM(amazon_sales[discounted_price])                     
- Total Discount Given  = SUM(amazon_sales[discount])           
- Average Discount%  = AVERAGE(amazon_sales[discountpercent])        
- Average Rating = AVERAGE(amazon_sales[rating])                         
- Total Reviews = SUM(amazon_sales[rating_count])       
- Top Product by Sales = RANKX(ALL(amazon_sales[product_name]), [Total Revenue], , DESC)

### 3. Visualizations Built

- Bar chart – Revenue by Category (Which product categories earn the highest revenue?)                      
- 100% Stacked Bar – Revenue vs. Discounts (Are discounts proportionate to revenue across categories?)   
- Word Cloud – Review title (High level Customer feedback?)           
- Table – Top Products by Revenue and it's avg rating - What are the top 10 revenue generating products?                
- Scatter Chart – Revenue vs Rating - How does each category perform in twerms of revenue and customer satisfaction?       
- KPI Cards - It shows What are the high-level metrics? 

Incorporated an interactive slicer that allows the dashboard metrics and chart to be displayed according to the product category.


### 4. Final Dashboard Preview

![dashboard](https://github.com/user-attachments/assets/269ab1d9-f94f-46c2-a52c-c065ebfc60f6)

---

### Key Insights for better decision making of the company

- Focus on enhancing the success of top-selling categories and items.  
- Modify discount approaches to boost profit margins.  
- Tackle categories that have low customer satisfaction yet offering significant discounts.  
- Employ customer terminology for more effective marketing and product communication.  
---

###  Tools Used

- Microsoft Power BI (Desktop)
- Power Query Editor
- DAX (Data Analysis Expressions)

---
