/*
 * Regression checks for the standalone address_standardizer C rule API.
 *
 * SQL tests cover the PostgreSQL extension surface.  This test calls
 * rules_add_rule() directly so the dependent library API cannot regress while
 * the SQL wrapper still behaves correctly.
 */

#include <stdio.h>
#include <string.h>

#include "gamma.h"
#include "pagc_api.h"
#include "pagc_std_api.h"

static int
check_rule(ERR_PARAM *err_p, const char *label, int expected, int *rule, int num)
{
	RULES *rules;
	char error_buf[MAXSTRLEN];
	int rc;

	memset(err_p, 0, sizeof(*err_p));
	memset(error_buf, 0, sizeof(error_buf));
	err_p->error_buf = error_buf;

	rules = rules_init(err_p);
	if (!rules)
	{
		fprintf(stderr, "%s: rules_init failed: %s\n",
		        label, err_p->err_array[err_p->last_err].content_buf);
		return 1;
	}

	rc = rules_add_rule(rules, num, rule);
	rules_free(rules);

	if ((rc == 0) != expected)
	{
		fprintf(stderr, "%s: rules_add_rule returned %d, expected %s",
		        label, rc, expected ? "success" : "failure");
		if (err_p->last_err)
			fprintf(stderr, ": %s", err_p->err_array[err_p->last_err].content_buf);
		fputc('\n', stderr);
		return 1;
	}

	return 0;
}

static int
check_maxnode_cleanup(ERR_PARAM *err_p)
{
	RULES *rules;
	char error_buf[MAXSTRLEN];

	memset(err_p, 0, sizeof(*err_p));
	memset(error_buf, 0, sizeof(error_buf));
	err_p->error_buf = error_buf;

	rules = rules_init(err_p);
	if (!rules)
	{
		fprintf(stderr, "max-node cleanup: rules_init failed: %s\n",
		        err_p->err_array[err_p->last_err].content_buf);
		return 1;
	}

	/*
	 * rules_add_rule() can leave last_node at MAXNODES after rejecting the
	 * next node.  rules_free() must clean only the MAXNODES allocated pointer
	 * slots, not last_node + 1.
	 */
	rules->last_node = MAXNODES;
	rules_free(rules);

	return 0;
}

int
main(void)
{
	ERR_PARAM err_p;
	int valid_extra[] = {1, -1, 5, -1, 4, 0};
	int invalid_high[] = {1, -1, 5, -1, MAX_CL, 0};
	int invalid_low[] = {1, -1, 5, -1, -1, 0};

	if (check_rule(&err_p, "valid EXTRA_C rule type", 1,
	               valid_extra, sizeof(valid_extra) / sizeof(valid_extra[0])))
		return 1;
	if (check_rule(&err_p, "invalid MAX_CL rule type", 0,
	               invalid_high, sizeof(invalid_high) / sizeof(invalid_high[0])))
		return 1;
	if (check_rule(&err_p, "invalid negative rule type", 0,
	               invalid_low, sizeof(invalid_low) / sizeof(invalid_low[0])))
		return 1;
	if (check_maxnode_cleanup(&err_p))
		return 1;

	return 0;
}
