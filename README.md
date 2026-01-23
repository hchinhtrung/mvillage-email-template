# M Village Email Templates

A comprehensive collection of email templates for M Village hotel booking platform, supporting multiple languages (English/Vietnamese) and various customer journey touchpoints.

## 📋 Table of Contents

- [Template Categories](#-template-categories)
- [Quick Start](#-quick-start)
- [Template Variables](#-template-variables)
- [Technical Specifications](#-technical-specifications)
- [Python Tools & Analytics](#-python-tools--analytics)
  - [Getting Started](#getting-started-with-python-tools)
  - [Available Tools](#available-tools)
- [Process Documentation](#-process-documentation)
- [Usage Guidelines](#-usage-guidelines)
- [Support](#-support)

## 📁 Template Categories

### 🏨 Booking Confirmations

- **1.bk-loyalty/** - Booking confirmations for loyalty program members
  - `bk-conf-EN.html` - English version
  - `bk-conf-VI.html` - Vietnamese version

- **2.bk-non-loyalty/** - Booking confirmations for non-loyalty customers
  - `bk-conf-non-loyalty-EN.html` - English version
  - `bk-conf-non-loyalty-VI.html` - Vietnamese version

- **3.bk-b2b/** - B2B booking confirmations
  - `bk-conf-b2b-EN.html` - English version
  - `bk-conf-b2b-VI.html` - Vietnamese version

### 🎯 Customer Journey & Onboarding

- **9.welcome/** - Welcome emails for new users
  - `email_welcome_en.html` - English welcome
  - `email_welcome_vi.html` - Vietnamese welcome

- **8.verify/** - Email verification
  - `verify.html` - Account verification email

- **10.remind-verify/** - Verification reminders
  - `remind-verify-EN.html` - English reminder
  - `remind-verify-VI.html` - Vietnamese reminder

- **22.pre-arrival-loyalty/** - Pre-arrival notifications for loyalty members
  - `pre-arrival-loyalty_en.html` - English pre-arrival
  - `pre-arrival-loyalty_vi.html` - Vietnamese pre-arrival

- **22.pre-arrival-non-loyalty/** - Pre-arrival notifications for non-loyalty customers
  - `pre-arrival-non-loyalty_en.html` - English pre-arrival
  - `pre-arrival-non-loyalty_vi.html` - Vietnamese pre-arrival

### 📊 Surveys & Feedback Collection

- **6.survey-loyalty/** - Post-stay surveys for loyalty members
  - `survey-loyalty-EN.html` - English survey
  - `survey-loyalty-VI.html` - Vietnamese survey

- **7.survey-non-loyalty/** - Post-stay surveys for non-loyalty customers
  - `survey-non-loyalty-EN.html` - English survey
  - `survey-non-loyalty-VI.html` - Vietnamese survey

- **17.start-review-loyalty/** - Review initiation for loyalty members
  - `start-review-loyalty-EN.html` - English version
  - `start-review-loyalty-VI.html` - Vietnamese version

- **18.end-review-loyalty/** - Review completion for loyalty members
  - `end-review-loyalty-EN.html` - English version
  - `end-review-loyalty-VI.html` - Vietnamese version

- **27.review-loyalty-v2/** - Updated review reminders for current users
  - `remind-current-user-en.html` - English reminder
  - `remind-current-user-vi.html` - Vietnamese reminder

- **29.survey-THY/** - THY survey templates with promotional variants
  - `survey-group1-EN.html` - Group 1 English survey
  - `survey-group1-VI.html` - Group 1 Vietnamese survey
  - `survey-group2-EN.html` - Group 2 English survey
  - `survey-group2-VI.html` - Group 2 Vietnamese survey
  - `promotion/` - Promotional survey variants

### 💰 Billing & Financial

- **5.einvoice/** - Electronic invoice templates
  - `einvoice-email.html` - Email invoice template
  - `einvoice-pms-template.html` - PMS invoice template
  - `einvoice-pms-updated.html` - Updated PMS template
  - `invoice-v2.html` - Version 2 invoice template

### 🏢 B2B & Corporate Solutions

- **4.b2b lead/** - B2B lead generation
  - `b2b.html` - B2B lead capture template

- **19.b2b-reminder/** - B2B follow-up reminders
  - `b2b-bao-gia.html` - Vietnamese pricing reminder
  - `b2b-reminder-v2-en.html` - English B2B reminder v2
  - `b2b-reminder-v2-vi.html` - Vietnamese B2B reminder v2

- **21.b2b-send-pass/** - B2B account credentials
  - `b2b-send-pass-en.html` - English credentials
  - `b2b-send-pass-vi.html` - Vietnamese credentials

- **24.b2b-recontact/** - B2B re-engagement
  - `b2b-combine.html` - Combined B2B recontact template

- **25.b2b-reminder-v3/** - Latest B2B reminder templates (Version 3)
  - `b2b-reminder-v3-en.html` - English B2B reminder v3
  - `b2b-reminder-v3-vi.html` - Vietnamese B2B reminder v3

### 🎖️ Loyalty Program Management

- **13.upgrade-tier/** - Tier upgrade notifications
  - `upgrade_tier_en.html` - English upgrade
  - `upgrade_tier_vi.html` - Vietnamese upgrade

- **14.downgrade-tier/** - Tier downgrade notifications
  - `downgrade_tier_en.html` - English downgrade
  - `downgrade_tier_vi.html` - Vietnamese downgrade

### 🏠 Property Management

- **23.landlord/** - Landlord-specific templates
  - `landlord.html` - Main landlord template
  - `landlord-demo.html` - Demo version

### 🎁 Special Campaigns

- **28.wrapped2025/** - Year-end 2025 wrapped campaign
  - `platinum-en.html` - Platinum tier English version
  - `platinum-vi.html` - Platinum tier Vietnamese version
  - `non-en.html` - Non-loyalty English version
  - `non-vi.html` - Non-loyalty Vietnamese version
  - `resend-platinum.html` - Platinum resend template

### 🎯 Project Savvy (Complete Email Suite)

- **26.project-savvy/** - Comprehensive Savvy hotel email templates
  - **bk-conf/** - Booking confirmations
    - `bk-conf-savvy-en-member.html` - Member English
    - `bk-conf-savvy-vi-member.html` - Member Vietnamese
    - `bk-conf-savvy-en-non-member.html` - Non-member English
    - `bk-conf-savvy-vi-non-member.html` - Non-member Vietnamese
    - `bk-conf-savvy-en-b2b.html` - B2B English
    - `bk-conf-savvy-vi-b2b.html` - B2B Vietnamese
  - **pre-arrival/** - Pre-arrival notifications
    - `pre-arrival-en-member.html` - Member English
    - `pre-arrival-vi-member.html` - Member Vietnamese
    - `pre-arrival-en-non-member.html` - Non-member English
    - `pre-arrival-vi-non-member.html` - Non-member Vietnamese
  - **thankyou/** - Post-stay thank you emails
    - `thankyou-en-member.html` - Member English
    - `thankyou-vi-member.html` - Member Vietnamese
    - `thankyou-en-non-member.html` - Non-member English
    - `thankyou-vi-non-member.html` - Non-member Vietnamese

### 🛠️ Tools & Utilities

- **12.tool/** - Utility templates and tools
  - `account_deletion_tool.html` - Account deletion template
  - `landlord-landing-page.html` - Landlord landing page
  - `original.html` - Original template
  - `survey-typeform-v1.html` - Typeform survey integration

### ⚠️ Issue Management

- **20.aware-issue/** - Issue awareness notifications
  - `aware-EN.html` - English issue notification
  - `aware-VI.html` - Vietnamese issue notification

## 🚀 Quick Start

### Using Templates

1. Choose the appropriate template from the categorized folders
2. Replace template variables with actual data
3. Test across different email clients
4. Deploy through your email service provider

### Template Variables

Most templates use Handlebars-style variables for dynamic content:

#### Common Variables

- `{{email}}` - Customer email address
- `{{name}}` - Customer full name
- `{{first_name}}` - Customer first name
- `{{last_name}}` - Customer last name
- `{{booking_id}}` - Booking reference number
- `{{hotel_name}}` - Hotel name
- `{{check_in_date}}` - Check-in date
- `{{check_out_date}}` - Check-out date
- `{{room_type}}` - Room type
- `{{total_amount}}` - Total booking amount
- `{{currency}}` - Currency code

#### B2B Specific Variables

- `{{company_name}}` - Company name
- `{{contact_person}}` - Contact person name
- `{{work_email}}` - Work email address
- `{{phone_number}}` - Phone number
- `{{hotel_city}}` - Hotel city location
- `{{budget_per_night}}` - Budget per night

## 🔧 Technical Specifications

### HTML & CSS Standards

- **HTML5** - Modern semantic HTML structure
- **CSS3** - Inline and embedded styles for maximum compatibility
- **Responsive Design** - Mobile-first approach with media queries
- **Cross-client Compatibility** - Tested across major email clients

### Email Client Support

- ✅ Outlook (2007-2019, Office 365)
- ✅ Gmail (Web, Mobile, Desktop)
- ✅ Apple Mail (macOS, iOS)
- ✅ Yahoo Mail
- ✅ Thunderbird
- ✅ Mobile clients (iOS Mail, Android Gmail)

### Typography & Branding

- **Primary Font**: Be Vietnam Pro (Google Fonts)
- **Fallback Fonts**: Arial, Helvetica, sans-serif
- **Character Encoding**: UTF-8
- **MIME Type**: text/html

### Performance Features

- **Optimized Images** - Compressed and web-optimized
- **Minified CSS** - Reduced file sizes
- **Fast Loading** - Optimized for quick rendering
- **Accessibility** - Screen reader friendly with proper ARIA labels

## 🤖 Python Tools & Analytics

The `15.python/` directory contains powerful Streamlit-based analytics tools and automation scripts for M Village operations.

### Getting Started with Python Tools

#### Prerequisites

- **Python Version**: 3.8 or higher
- **Package Manager**: pip

#### Installation

1. **Navigate to the Python tools directory:**

   ```bash
   cd 15.python
   ```

2. **Create a virtual environment (recommended):**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install required dependencies:**
   ```bash
   pip install streamlit pandas numpy altair requests
   ```

#### Running Streamlit Apps

All interactive tools use Streamlit. To run any tool:

```bash
streamlit run <tool-name>.py
```

The app will automatically open in your default browser at `http://localhost:8501`

### Available Tools

#### 📊 Analytics & Reporting Tools

##### **mv-tool-1.py** - Recruit Signup & CR Analyzer

**Purpose**: Analyze hotel signup conversion rates and performance metrics

**Usage:**

```bash
streamlit run mv-tool-1.py
```

**Features:**

- Upload signup and reservation CSV/Excel files
- Calculate conversion rates (CR) by hotel, city, and brand
- Overall performance summary with key metrics
- Hotel ranking (overall, by city, by brand model)
- Interactive date range filtering
- Visual dashboards with metrics

**Input Requirements:**

- Signup file with columns: `hotel_short_name`, `city`, date column (E), count column (F)
- Reservation file with columns: `Hotel Name`, `City`, `tenant_id`, `Checkin`, brand model (B)

---

##### **mv-tool-2.py** - Hotel Signup Ranking Movement

**Purpose**: Track week-over-week ranking changes and performance trends

**Usage:**

```bash
streamlit run mv-tool-2.py
```

**Features:**

- Compare last week vs. this week performance
- Track ranking movements (up/down/new entries)
- CR% change analysis
- Global and city-level ranking comparisons
- Brand model segmentation
- Movement indicators (↑ Up, ↓ Down, → No Change, 🆕 New Entry)

**Input Requirements:**

- Two CSV files: last week and current week rankings
- Required columns: `Rank`, `Hotel`, `Brand Model`, `City`, `Signups`, `Check-ins`

---

##### **mv-tool-2-1.py** - Weekly Ranking Comparison Dashboard

**Purpose**: Advanced weekly comparison with styled visualizations

**Usage:**

```bash
streamlit run mv-tool-2-1.py
```

**Features:**

- Dual-period comparison (select any two date ranges)
- Global, city, and city-brand ranking analysis
- Color-coded performance indicators
- Styled dataframes with custom headers
- Comprehensive city overview with metrics
- Export-ready formatted tables

**Input Requirements:**

- Signup file with date and count columns
- Reservation file with hotel, city, and check-in data

---

##### **mv-tool-3.py** - Daily Recruit Funnel Dashboard

**Purpose**: Daily signup funnel analysis with week-over-week metrics

**Usage:**

```bash
streamlit run mv-tool-3.py
```

**Features:**

- Daily signup funnel breakdown by status
- Status categories: "Chưa Sign-up", "Đã Sign-up từ trước", "Sign-up sau C/I"
- City-level segmentation (HCM, HN, DN)
- Week-over-week (WoW) new recruit comparison
- Automatic weekly period calculation
- CSV export functionality

**Input Requirements:**

- Signup file with columns: `checkin`, `city`, `Sign up status v2`, count column (E)

---

##### **mv-tool-4.py** - Executive BI Dashboard

**Purpose**: Executive-level weekly performance overview with visualizations

**Usage:**

```bash
streamlit run mv-tool-4.py
```

**Features:**

- Executive scorecards with key KPIs
- Weekly signup trend charts (Altair visualizations)
- City performance heatmaps
- Top/bottom movers analysis (rank gainers/losers)
- Hotel ranking trend over time
- Interactive filters for city and hotel selection
- Week-over-week performance metrics

**Input Requirements:**

- Signup file with hotel, city, brand model, date, and count data

---

#### 🔧 Utility Scripts

##### **agoda_review.py** - Agoda Guest Type Analyzer

**Purpose**: Analyze guest type distribution from Agoda reviews via API

**Usage:**

```bash
streamlit run agoda_review.py
```

**Features:**

- API-based analysis (no web scraping required)
- No property ID needed - just paste Agoda URLs
- Guest type breakdown: Solo, Couple, Family, Group, Business
- Insight layer with guest mix classification
- Percentage analysis (Couple %, Business %)
- CSV export for further analysis
- Batch processing of multiple hotels

**Input Requirements:**

- Agoda hotel URLs (one per line)

---

##### **send-b2b-lead.py** - B2B Lead Email Automation

**Purpose**: Automated B2B lead email sending

**Usage:**

```bash
python send-b2b-lead.py
```

**Features:**

- CSV data import for batch processing
- API integration with M Village backend
- Error handling and retry logic
- Success/failure logging

---

##### **detect_booking_id.py** - Booking ID Detection

**Purpose**: Utility for detecting and validating booking IDs

**Usage:**

```bash
python detect_booking_id.py
```

---

##### **process-csv.py** - CSV Processing Utility

**Purpose**: General CSV data processing and transformation

**Usage:**

```bash
python process-csv.py
```

---

##### **retry.py** - Retry Logic Utility

**Purpose**: Helper module for implementing retry logic in API calls

---

#### 📓 Data Analysis Notebooks

##### **Updated_Trip - VAT.ipynb** - Jupyter Notebook

**Purpose**: Data analysis and VAT calculations for trip data

**Usage:**

```bash
jupyter notebook "Updated_Trip - VAT.ipynb"
```

**Features:**

- Trip data analysis
- VAT calculations and reporting
- Data visualization
- Export capabilities

---

### Tool Selection Guide

| Use Case                       | Recommended Tool                   |
| ------------------------------ | ---------------------------------- |
| Analyze hotel conversion rates | `mv-tool-1.py`                     |
| Track weekly ranking changes   | `mv-tool-2.py` or `mv-tool-2-1.py` |
| Monitor daily signup funnel    | `mv-tool-3.py`                     |
| Executive performance overview | `mv-tool-4.py`                     |
| Understand guest demographics  | `agoda_review.py`                  |
| Send B2B lead emails           | `send-b2b-lead.py`                 |

### Tips for Using Python Tools

1. **Data Format**: Ensure your CSV/Excel files match the expected column structure
2. **Date Formats**: Tools auto-detect dates, but consistent formatting helps
3. **File Size**: Streamlit apps handle files up to 200MB by default
4. **Export Data**: Most tools include CSV download buttons for results
5. **Browser Compatibility**: Works best in Chrome, Firefox, or Edge

## 📈 Process Documentation

### Flowcharts

- **16.flowchart-mermaidchart/MV-pickup-profile.mmd** - Profile pickup process flowchart
- **16.flowchart-mermaidchart/MV-product-process.mmd** - Product development process flowchart

These Mermaid charts document the internal processes and can be rendered using Mermaid-compatible tools.

## 📝 Usage Guidelines

### Best Practices

1. **Always test templates** in multiple email clients before deployment
2. **Use semantic HTML** for better accessibility and deliverability
3. **Optimize images** for web delivery (WebP, compressed JPEG/PNG)
4. **Maintain consistent branding** across all templates
5. **Follow responsive design** principles for mobile compatibility

### Customization

- Templates are designed to be easily customizable
- Maintain the core structure while updating content and styling
- Test thoroughly after any modifications
- Keep backup copies of original templates

### Language Support

- **English (EN)** - Full English templates with proper grammar and tone
- **Vietnamese (VI)** - Full Vietnamese templates with cultural considerations
- **Bilingual Consistency** - Maintained messaging and branding across languages

## 🎨 Design Features

### Visual Elements

- **Professional Layout** - Clean, modern design aesthetic
- **Brand Consistency** - M Village colors, fonts, and imagery
- **Responsive Grid** - Adapts to different screen sizes
- **Call-to-Action Buttons** - Prominent, accessible action buttons

### Accessibility

- **Screen Reader Support** - Proper ARIA labels and semantic HTML
- **High Contrast** - Readable color combinations
- **Keyboard Navigation** - Accessible via keyboard controls
- **Alt Text** - Descriptive alternative text for images

## 📞 Support & Maintenance

### Getting Help

For questions about template usage, customization, or technical issues:

- Contact the M Village development team
- Check existing documentation in this repository
- Review the process flowcharts for workflow guidance

### Contributing

When adding new templates or modifying existing ones:

1. Follow the established naming conventions
2. Maintain bilingual support (EN/VI)
3. Test across multiple email clients
4. Update this README with new template information
5. Follow the existing folder structure and organization

### Version Control

- All templates are version controlled in Git
- Use descriptive commit messages
- Tag major releases and updates
- Maintain backward compatibility when possible

---

**Last Updated**: January 2025  
**Version**: 2.1  
**Maintained by**: M Village Development Team
